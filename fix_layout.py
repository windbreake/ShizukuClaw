import re

with open('src/static/control_panel.html', 'r', encoding='utf-8') as f:
    text = f.read()

# For these tabs: v-dashboard, v-launcher, v-agent, v-env-check, v-system, v-database, v-logs
# We want to wrap everything after their <h3>...</h3> into a <div class="col-xxl-10 mb-4 mx-auto">
# Actually, the <h3> can also be wrapped.
# But it's easier to just wrap the whole content of the tab-pane inside a div, OR just add a class to the row/cards.
# Wait! Instead of changing every tab manually, what if we just constrain the max width of the #content?
