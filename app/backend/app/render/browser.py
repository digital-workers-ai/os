from pathlib import Path

from app.render.clients import Browser, RenderError


class OverflowError(RenderError):
    def __init__(self, findings: list[dict]):
        self.findings = findings
        super().__init__(describe(findings))


def describe(findings: list[dict]) -> str:
    lines = [f"{len(findings)} line(s) of copy overflow their container:"]
    lines += [
        f"  {finding['scene']} .{finding['cls']}: {finding['text']!r} "
        f"({finding['chars']} chars, {finding['width']}px in "
        f"{finding['available']}px — {finding['over']}px over)"
        for finding in findings
    ]
    return "\n".join(lines)


def screenshot(html_path: Path, dest: Path, *, width, height, client=None) -> Path:
    client = client or Browser()
    return client.shot(
        Path(html_path).resolve().as_uri(), dest, width=width, height=height
    )


def overflow(html_path: Path, *, frame_width: int, client=None) -> list[dict]:
    client = client or Browser()
    return client.measure(Path(html_path).resolve().as_uri(), frame_width=frame_width)


def refuse_overflow(html_path: Path, *, frame_width: int, client=None) -> None:
    findings = overflow(html_path, frame_width=frame_width, client=client)
    if findings:
        raise OverflowError(findings)
