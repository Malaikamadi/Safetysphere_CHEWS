import os
import glob

# The new sidebar HTML
NEW_SIDEBAR = """    <aside class="sidebar" id="sidebar">
      <div class="sidebar__header"><a href="index.html" class="sidebar__brand"><div class="sidebar__icon"><i data-lucide="globe"></i></div><div><div class="sidebar__title">CHEWS</div><div class="sidebar__version">v3.0 · Intelligence Platform</div></div></a></div>
      <nav class="sidebar__nav">
        <div class="nav-section"><div class="nav-section__label">Overview</div>
          <a href="index.html" class="nav-link"><span class="nav-link__icon"><i data-lucide="crosshair"></i></span> Command Center</a>
        </div>
        
        <div class="nav-section">
          <div class="nav-group {strat_active}">
            <button class="nav-link nav-group__toggle" onclick="this.parentElement.classList.toggle('is-expanded')">
              <span class="nav-link__icon"><i data-lucide="map"></i></span>
              <span class="nav-link__text">Strategic Planning</span>
              <i data-lucide="chevron-down" class="nav-group__chevron"></i>
            </button>
            <div class="nav-group__content">
              <a href="strategic.html#vulnerability" class="nav-sublink">Vulnerability Score</a>
              <a href="strategic.html#hazard" class="nav-sublink">Hazard Map</a>
              <a href="strategic.html#pollution" class="nav-sublink">Pollution Hotspot</a>
              <a href="strategic.html#carbon" class="nav-sublink">Carbon Footprint</a>
            </div>
          </div>
          
          <div class="nav-group {ew_active}">
            <button class="nav-link nav-group__toggle" onclick="this.parentElement.classList.toggle('is-expanded')">
              <span class="nav-link__icon"><i data-lucide="zap"></i></span>
              <span class="nav-link__text">Early Warning</span>
              <i data-lucide="chevron-down" class="nav-group__chevron"></i>
            </button>
            <div class="nav-group__content">
              <a href="early-warning.html" class="nav-sublink">Warning Center</a>
            </div>
          </div>

          <div class="nav-group {health_active}">
            <button class="nav-link nav-group__toggle" onclick="this.parentElement.classList.toggle('is-expanded')">
              <span class="nav-link__icon"><i data-lucide="hospital"></i></span>
              <span class="nav-link__text">Healthcare Readiness</span>
              <i data-lucide="chevron-down" class="nav-group__chevron"></i>
            </button>
            <div class="nav-group__content">
              <a href="healthcare.html#forecast" class="nav-sublink">Disease Forecast</a>
              <a href="healthcare.html#anomaly" class="nav-sublink">Anomaly Detection</a>
              <a href="healthcare.html#surge" class="nav-sublink">Surge Planning</a>
            </div>
          </div>

          <div class="nav-group {poc_active}">
            <button class="nav-link nav-group__toggle" onclick="this.parentElement.classList.toggle('is-expanded')">
              <span class="nav-link__icon"><i data-lucide="pill"></i></span>
              <span class="nav-link__text">Point-of-Care</span>
              <i data-lucide="chevron-down" class="nav-group__chevron"></i>
            </button>
            <div class="nav-group__content">
              <a href="point-of-care.html#triage" class="nav-sublink">Multilingual Triage</a>
              <a href="point-of-care.html#assistant" class="nav-sublink">Health Assistant</a>
            </div>
          </div>
        </div>
      </nav>
      <div class="sidebar__footer"><div class="sidebar__status"><span class="pulse-dot"></span><span>System Online · Sierra Leone</span></div></div>
    </aside>"""

for root, _, files in os.walk('/Users/malaikamadi/SafetySphere_CHEWS/frontend'):
    for f in files:
        if f.endswith('.html'):
            filepath = os.path.join(root, f)
            with open(filepath, 'r') as file:
                content = file.read()
            
            # Find the existing aside
            start_idx = content.find('<aside class="sidebar" id="sidebar">')
            end_idx = content.find('</aside>') + len('</aside>')
            
            if start_idx != -1 and end_idx != -1:
                # Determine active state
                strat_active = 'is-expanded' if f == 'strategic.html' else ''
                ew_active = 'is-expanded' if f == 'early-warning.html' else ''
                health_active = 'is-expanded' if f == 'healthcare.html' else ''
                poc_active = 'is-expanded' if f == 'point-of-care.html' else ''
                
                new_aside = NEW_SIDEBAR.format(
                    strat_active=strat_active,
                    ew_active=ew_active,
                    health_active=health_active,
                    poc_active=poc_active
                )
                
                content = content[:start_idx] + new_aside + content[end_idx:]
                
                # Also remove "Area X" from topbar
                content = content.replace('Area 1 — ', '')
                content = content.replace('Area 2 — ', '')
                content = content.replace('Area 3 — ', '')
                content = content.replace('Area 4 — ', '')
                
                with open(filepath, 'w') as file:
                    file.write(content)

print("Sidebar updated.")
