import ast
import os

ADMIN_SOURCE = os.path.join(os.path.dirname(__file__), "..", "app", "routers", "admin.py")

SECRET_SETTINGS = {
    "jwt_secret",
    "webhook_secret",
    "billing_webhook_secret",
    "database_url",
    "redis_url",
    "aws_access_key_id",
    "aws_secret_access_key",
}


def _debug_config_body() -> ast.FunctionDef:
    tree = ast.parse(open(ADMIN_SOURCE, "r", encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "debug_config":
            return node
    raise AssertionError("debug_config endpoint not found")


def _returned_settings_attrs(func: ast.FunctionDef) -> set[str]:
    """Settings attributes whose value is returned verbatim by the endpoint."""
    redacted = {
        id(arg)
        for node in ast.walk(func)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "bool"
        for arg in node.args
    }
    return {
        node.attr
        for node in ast.walk(func)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "settings"
        and id(node) not in redacted
    }


def test_debug_config_does_not_return_secret_values():
    leaked = _returned_settings_attrs(_debug_config_body()) & SECRET_SETTINGS
    assert not leaked, f"debug endpoint returns secret values: {sorted(leaked)}"
