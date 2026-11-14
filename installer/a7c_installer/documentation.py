"""User guides resolve inside a frozen App or from the source tree."""
from pathlib import Path

GUIDES = {
    '开始使用': 'START_HERE.md',
    '卸载与恢复': 'RECOVERY.md',
    '试用范围': 'SHARING.md',
    '反馈问题': 'FEEDBACK.md',
    '第三方许可': 'THIRD_PARTY.md',
    '项目许可': 'LICENSE',
    '版本与验收': 'validation.json',
}


def read_guide(name):
    if name not in GUIDES.values():
        raise ValueError('Unknown bundled guide')
    packaged = Path(__file__).resolve().parent / 'resources/help'
    root = packaged if packaged.is_dir() else Path(__file__).resolve().parents[1]
    if name == 'LICENSE' and not packaged.is_dir():
        root = root.parent
    value = (root / name).read_text(encoding='utf-8')
    return '```json\n' + value + '\n```' if name.endswith('.json') else value
