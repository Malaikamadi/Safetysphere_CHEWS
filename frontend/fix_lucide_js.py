import os
import re

for filepath in [
    'app.js', 'strategic.js', 'early-warning.js', 'healthcare.js', 'point-of-care.js'
]:
    with open(filepath, 'r') as f:
        content = f.read()

    # Find functions that end with 'el.innerHTML = html;' or '...appendChild...'
    # A simple hack: just search for all function definitions that seem to render, and add setTimeout(lucide.createIcons, 0); at the end.
    
    # We can just replace common end-of-render patterns:
    content = content.replace('el.innerHTML = html;', 'el.innerHTML = html;\n  if (window.lucide) lucide.createIcons();')
    content = content.replace('feed.innerHTML = data.alerts.map(a => renderAlertItem(a)).join("");', 'feed.innerHTML = data.alerts.map(a => renderAlertItem(a)).join("");\n    if (window.lucide) lucide.createIcons();')
    content = content.replace('modelCards.appendChild(card);', 'modelCards.appendChild(card);\n    if (window.lucide) lucide.createIcons();')
    content = content.replace('recsLi.appendChild(li);\n  });', 'recsLi.appendChild(li);\n  });\n  if (window.lucide) lucide.createIcons();')
    content = content.replace('factorsList.appendChild(li);\n  });', 'factorsList.appendChild(li);\n  });\n  if (window.lucide) lucide.createIcons();')
    
    with open(filepath, 'w') as f:
        f.write(content)

print("Fixed JS rendering for Lucide.")
