"""Explicit, deterministic cleanup of a user-selected text range."""
import re


def clean_selection(text, *, remove_line_numbers=False, join_lines=False):
    if remove_line_numbers:
        # Require an explicit numbered-list delimiter; do not remove IDs or dates.
        text = re.sub(r'(?m)^[ \t]*[1-9][0-9]{0,5}[.):：][ \t]', '', text)
    if join_lines:
        text = text.replace('\n', ' ')
    return text
