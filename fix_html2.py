import sys
import re

path = 'src/static/control_panel.html'
with open(path, 'r', encoding='utf-8') as f:
    original = f.read()

# I will find all instances of '?' that appear suspiciously and fix them.
# The previous regex might not have caught all.
# Let's read from the oldest vs code history to get the pure text.
