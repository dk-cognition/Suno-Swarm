"""Safe extraction helpers for uploaded sample-pack archives."""
import os
import tempfile
import zipfile
from typing import BinaryIO, List, Tuple


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_MEMBER_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_MEMBER_COUNT = 1000
COPY_CHUNK_BYTES = 64 * 1024


class SamplePackValidationError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _safe_member_path(destination: str, member: str) -> str:
    invalid_name = (
        not member
        or "\x00" in member
        or os.path.isabs(member)
        or member.startswith(("\\", "//"))
    )
    if invalid_name:
        raise SamplePackValidationError(400, f"unsafe path in archive: {member}")

    resolved_destination = os.path.realpath(destination)
    target = os.path.realpath(os.path.join(resolved_destination, member))
    try:
        contained = os.path.commonpath([resolved_destination, target]) == resolved_destination
    except ValueError:
        contained = False
    if not contained or target == resolved_destination:
        raise SamplePackValidationError(400, f"unsafe path in archive: {member}")
    return target


def _archive_members(
    archive: zipfile.ZipFile, destination: str
) -> List[Tuple[zipfile.ZipInfo, str]]:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBER_COUNT:
        raise SamplePackValidationError(400, "archive has too many entries")

    members = []
    total_bytes = 0
    for info in infos:
        if info.is_dir():
            continue
        if info.file_size > MAX_MEMBER_BYTES:
            raise SamplePackValidationError(413, "archive member too large")
        total_bytes += info.file_size
        if total_bytes > MAX_TOTAL_BYTES:
            raise SamplePackValidationError(413, "archive contents too large")
        members.append((info, _safe_member_path(destination, info.filename)))
    return members


def _extract_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, target: str) -> int:
    os.makedirs(os.path.dirname(target), exist_ok=True)
    member_bytes = 0
    temporary_path = ""
    try:
        with archive.open(info) as source, tempfile.NamedTemporaryFile(
            dir=os.path.dirname(target),
            prefix=".samplepack-",
            delete=False,
        ) as output:
            temporary_path = output.name
            while chunk := source.read(COPY_CHUNK_BYTES):
                member_bytes += len(chunk)
                if member_bytes > MAX_MEMBER_BYTES:
                    raise SamplePackValidationError(413, "archive member too large")
                output.write(chunk)
        os.replace(temporary_path, target)
        return member_bytes
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


def extract_sample_pack(upload_file: BinaryIO, destination: str) -> List[str]:
    os.makedirs(destination, exist_ok=True)
    extracted = []
    with tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b") as temporary_zip:
        written = 0
        while chunk := upload_file.read(COPY_CHUNK_BYTES):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise SamplePackValidationError(413, "upload too large")
            temporary_zip.write(chunk)
        temporary_zip.seek(0)

        try:
            with zipfile.ZipFile(temporary_zip) as archive:
                members = _archive_members(archive, destination)
                total_bytes = 0
                for info, target in members:
                    total_bytes += _extract_member(archive, info, target)
                    if total_bytes > MAX_TOTAL_BYTES:
                        os.remove(target)
                        raise SamplePackValidationError(413, "archive contents too large")
                    extracted.append(info.filename)
        except zipfile.BadZipFile:
            raise SamplePackValidationError(400, "invalid zip archive")
    return extracted
