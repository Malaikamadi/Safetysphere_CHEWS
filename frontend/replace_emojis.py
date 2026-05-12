import os
import glob

# Emoji to Lucide Icon mapping
EMOJI_MAP = {
    "🌍": '<i data-lucide="globe"></i>',
    "🎯": '<i data-lucide="crosshair"></i>',
    "🗺️": '<i data-lucide="map"></i>',
    "⚡": '<i data-lucide="zap"></i>',
    "🏥": '<i data-lucide="hospital"></i>',
    "💊": '<i data-lucide="pill"></i>',
    "🇸🇱": '', # Remove flag or replace with SL text
    "🦟": '<i data-lucide="bug"></i>',
    "🌊": '<i data-lucide="waves"></i>',
    "🌡️": '<i data-lucide="thermometer"></i>',
    "💨": '<i data-lucide="wind"></i>',
    "🧠": '<i data-lucide="brain"></i>',
    "✅": '<i data-lucide="check-circle"></i>',
    "💬": '<i data-lucide="message-square"></i>',
    "🚨": '<i data-lucide="alert-triangle"></i>',
    "⚙️": '<i data-lucide="settings"></i>',
    "🏗️": '<i data-lucide="building"></i>',
    "👥": '<i data-lucide="users"></i>',
    "🏭": '<i data-lucide="factory"></i>',
    "🌱": '<i data-lucide="leaf"></i>',
    "⛽": '<i data-lucide="fuel"></i>',
    "📋": '<i data-lucide="clipboard-list"></i>',
    "🛏️": '<i data-lucide="bed"></i>',
    "👩‍⚕️": '<i data-lucide="stethoscope"></i>',
    "🩺": '<i data-lucide="stethoscope"></i>',
    "🤒": '<i data-lucide="thermometer"></i>',
    "👤": '<i data-lucide="user"></i>',
    "📈": '<i data-lucide="trending-up"></i>',
    "🔍": '<i data-lucide="search"></i>',
    "🦠": '<i data-lucide="virus"></i>',
    "☀️": '<i data-lucide="sun"></i>',
    "🔔": '<i data-lucide="bell"></i>',
    "🔴": '<i data-lucide="alert-circle" class="text-danger"></i>',
    "🟠": '<i data-lucide="alert-triangle" class="text-warning"></i>',
    "🟡": '<i data-lucide="info" class="text-warning"></i>',
    "🔵": '<i data-lucide="info" class="text-accent-2"></i>',
    "ℹ️": '<i data-lucide="info"></i>',
    "🚑": '<i data-lucide="ambulance"></i>',
    "📉": '<i data-lucide="trending-down"></i>',
    "➡️": '<i data-lucide="arrow-right"></i>',
    "📊": '<i data-lucide="bar-chart-2"></i>',
    "📅": '<i data-lucide="calendar"></i>',
    "⚠️": '<i data-lucide="alert-triangle"></i>',
    "🌧️": '<i data-lucide="cloud-rain"></i>',
    "💧": '<i data-lucide="droplet"></i>',
    "🛡️": '<i data-lucide="shield"></i>',
    "🧒": '<i data-lucide="baby"></i>',
    "📍": '<i data-lucide="map-pin"></i>',
    "📡": '<i data-lucide="radio"></i>',
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # If HTML, insert Lucide script before closing body
    if filepath.endswith('.html'):
        if '<script src="https://unpkg.com/lucide@latest"></script>' not in content:
            content = content.replace('</body>', '  <script src="https://unpkg.com/lucide@latest"></script>\n  <script>lucide.createIcons();</script>\n</body>')

    # If JS, we need to handle emojis inside strings carefully, replacing with HTML tags
    # that Lucide can process, but since JS might render them dynamically, we should
    # ensure `lucide.createIcons()` is called after rendering.
    
    for emoji, icon in EMOJI_MAP.items():
        content = content.replace(emoji, icon)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for root, _, files in os.walk('/Users/malaikamadi/SafetySphere_CHEWS/frontend'):
    for f in files:
        if f.endswith(('.html', '.js')):
            process_file(os.path.join(root, f))
print("Done processing files.")
