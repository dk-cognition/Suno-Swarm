"""Seed a demo workspace, users, prompts and tracks into a local database."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

from app.core.db import SessionLocal, init_db  # noqa: E402
from app.core.security import generate_token, hash_password  # noqa: E402
from app.models.models import (  # noqa: E402
    Prompt,
    RenderJob,
    ShareLink,
    Stem,
    Track,
    User,
    Workspace,
)

DEMO_PROMPTS = [
    ("Neon Dusk", "synthwave drive at sunset, analog pads, gated snare", "synthwave", 112),
    ("Paper Lanterns", "dream pop with shoegaze guitars, airy female vocals", "dream-pop", 96),
    ("Basement Tape", "lo-fi hiphop, dusty vinyl crackle, upright bass", "lo-fi-hiphop", 84),
]


def main() -> None:
    init_db()
    session = SessionLocal()

    workspace = Workspace(name="Demo Studio", plan="pro", credit_balance=500)
    session.add(workspace)
    session.flush()

    owner = User(
        workspace_id=workspace.id,
        email="artist@example.com",
        password_hash=hash_password("hunter2"),
        display_name="Demo Artist",
        avatar_url="https://cdn.example.com/avatars/demo.png",
        refresh_token=generate_token(),
    )
    admin = User(
        workspace_id=workspace.id,
        email="ops@example.com",
        password_hash=hash_password("opsops"),
        display_name="Ops",
        is_admin=True,
        refresh_token=generate_token(),
    )
    session.add_all([owner, admin])
    session.flush()

    for title, text, genre, bpm in DEMO_PROMPTS:
        prompt = Prompt(
            user_id=owner.id, text=text, genre=genre, bpm=bpm, moderation_state="allowed"
        )
        session.add(prompt)
        session.flush()

        job = RenderJob(prompt_id=prompt.id, workspace_id=workspace.id, status="complete")
        session.add(job)
        session.flush()

        track = Track(
            workspace_id=workspace.id,
            job_id=job.id,
            title=title,
            prompt_text=text,
            tags=[genre],
            visibility="public",
            duration_seconds=120,
            model_version="swarm-diffusion-2.3",
            mixdown_key=f"workspaces/{workspace.id}/tracks/{job.id}/mixdown.wav",
        )
        session.add(track)
        session.flush()

        for stem_name in ("vocals", "drums", "bass", "other"):
            session.add(
                Stem(
                    track_id=track.id,
                    name=stem_name,
                    object_key=(
                        f"workspaces/{workspace.id}/tracks/{track.id}/stems/{stem_name}.wav"
                    ),
                )
            )
        session.add(ShareLink(slug=generate_token(10), track_id=track.id))

    session.commit()
    print(f"seeded workspace={workspace.id} user=artist@example.com password=hunter2")


if __name__ == "__main__":
    main()
