import os
import sys
import base64
import requests
from io import BytesIO
from PIL import Image, ImageDraw

# Try to import fonttools, warn if missing but continue
try:
    from fontTools import subset
    from fontTools.ttLib import TTFont
except ImportError:
    subset = None
    print("Warning: fonttools not installed, font subsetting will be skipped.")

GITHUB_TOKEN = os.getenv("GH_PAT")
USERNAME = "Parin070"

# Colors and configuration
BG_COLOR = "transparent"
TEXT_COLOR = "#c9d1d9"
ACCENT_COLOR = "#58a6ff"
FONT_URL = "https://github.com/JetBrains/JetBrainsMono/raw/master/fonts/ttf/JetBrainsMono-Regular.ttf"
FONT_PATH = "JetBrainsMono-Regular.ttf"

def download_font():
    if not os.path.exists(FONT_PATH):
        print("Downloading JetBrains Mono...")
        r = requests.get(FONT_URL)
        with open(FONT_PATH, 'wb') as f:
            f.write(r.content)

def subset_font(text):
    if not subset or not os.path.exists(FONT_PATH):
        return ""
    
    unique_chars = "".join(set(text))
    # We use a temporary file for the subsetted font
    subset_path = "subset.ttf"
    
    options = subset.Options()
    options.flavor = "woff2"
    
    font = TTFont(FONT_PATH)
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=unique_chars)
    subsetter.subset(font)
    
    buf = BytesIO()
    font.save(buf)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    font.close()
    
    return f"data:font/woff2;charset=utf-8;base64,{b64}"

def get_base_svg(width, height, font_b64, extra_css=""):
    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    @font-face {{
      font-family: 'JetBrains Mono';
      src: url('{font_b64}') format('woff2');
      font-weight: normal;
      font-style: normal;
    }}
    .text {{
      font-family: 'JetBrains Mono', monospace;
      fill: {TEXT_COLOR};
    }}
    .accent {{
      fill: {ACCENT_COLOR};
    }}
    {extra_css}
    @media (prefers-color-scheme: light) {{
        .text {{ fill: #24292e; }}
        .accent {{ fill: #0969da; }}
    }}
  </style>
"""

def generate_header(filename, text, width=620, height=40):
    print(f"Generating {filename}...")
    font_b64 = subset_font(text)
    svg = get_base_svg(width, height, font_b64)
    # 20px font, vertically centered
    svg += f'  <text x="0" y="28" font-size="20" class="text accent" font-weight="bold">{text}</text>\n'
    svg += "</svg>"
    
    with open(f"../{filename}", "w", encoding="utf-8") as f:
        f.write(svg)

def generate_ascii(image_path="headshot.jpg"):
    print("Generating ascii.svg...")
    if not os.path.exists(image_path):
        print(f"Image {image_path} not found, skipping ASCII generation.")
        # Create a placeholder
        font_b64 = subset_font("PLACEHOLDER")
        svg = get_base_svg(460, 460, font_b64)
        svg += '  <rect width="460" height="460" fill="#161b22" rx="10"/>\n'
        svg += f'  <text x="230" y="230" font-size="24" class="text" text-anchor="middle">Missing {image_path}</text>\n'
        svg += "</svg>"
        with open("../ascii.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        return

    # Character ramp from dark to light
    ramp = " .:+*?%S#@"
    
    img = Image.open(image_path).convert("L")
    # Resize to fit grid, roughly 50x50 characters
    cols = 55
    # Font aspect ratio compensation (characters are taller than they are wide)
    char_aspect = 0.5
    w, h = img.size
    rows = int((h / w) * cols * char_aspect)
    
    img = img.resize((cols, rows), Image.Resampling.LANCZOS)
    pixels = img.load()
    
    lines = []
    unique_chars = set()
    for y in range(rows):
        line = ""
        for x in range(cols):
            val = pixels[x, y]
            idx = int((val / 255.0) * (len(ramp) - 1))
            char = ramp[idx]
            line += char
            unique_chars.add(char)
        lines.append(line)
        
    font_b64 = subset_font("".join(unique_chars) + " ")
    
    width = 460
    height = 460
    
    # 8px font size, 10px line height
    font_size = 9
    line_height = 10
    start_y = (height - (rows * line_height)) // 2 + font_size
    
    svg = get_base_svg(width, height, font_b64)
    # Adding a subtle background for the ascii
    svg += '  <rect width="460" height="460" fill="transparent" rx="10"/>\n'
    
    for i, line in enumerate(lines):
        y = start_y + (i * line_height)
        # Using xml:space="preserve" to keep whitespace
        svg += f'  <text x="20" y="{y}" font-size="{font_size}" class="text" xml:space="preserve">{line}</text>\n'
        
    svg += "</svg>"
    with open("../ascii.svg", "w", encoding="utf-8") as f:
        f.write(svg)

def fetch_github_data():
    if not GITHUB_TOKEN:
        print("GH_TOKEN not set, returning mock data.")
        return {"contributions": []}
    
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    query = """
    {
      user(login: "%s") {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """ % USERNAME
    
    r = requests.post("https://api.github.com/graphql", json={"query": query}, headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        print("Failed to fetch data:", r.text)
        return None

def generate_stats_and_year(data):
    print("Generating stats.svg and year.svg...")
    
    # Mock data if API fails or no token
    days = []
    if data and "data" in data and data["data"]["user"]:
        weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for day in week["contributionDays"]:
                days.append(day["contributionCount"])
    else:
        # Generate 365 days of random data
        import random
        days = [random.randint(0, 10) for _ in range(365)]
    
    total = sum(days)
    
    # year.svg - character per day
    ramp = " .+#@"
    year_lines = []
    cols = 52
    rows = 7
    chars_used = set(ramp + f"Total Contributions: {total}")
    font_b64 = subset_font("".join(chars_used))
    
    svg = get_base_svg(620, 150, font_b64)
    svg += f'  <text x="0" y="20" font-size="14" class="text">Last Year Contributions ({total})</text>\n'
    
    start_x = 0
    start_y = 40
    char_width = 11
    char_height = 14
    
    max_count = max(days) if days else 1
    
    day_idx = 0
    for c in range(cols):
        for r in range(rows):
            if day_idx < len(days):
                count = days[day_idx]
                idx = 0
                if count > 0:
                    idx = int((count / max_count) * (len(ramp) - 2)) + 1
                    idx = min(idx, len(ramp) - 1)
                char = ramp[idx]
                x = start_x + (c * char_width)
                y = start_y + (r * char_height)
                color_class = "accent" if count > 0 else "text"
                opacity = 1.0 if count > 0 else 0.3
                svg += f'  <text x="{x}" y="{y}" font-size="12" class="{color_class}" opacity="{opacity}">{char}</text>\n'
                day_idx += 1
                
    svg += "</svg>"
    with open("../year.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    # stats.svg - simple bar chart or sparkline
    # For a monospace aesthetic, let's make it a line graph
    font_b64 = subset_font(f"Activity Graph {total} contributions")
    svg2 = get_base_svg(620, 150, font_b64, extra_css=".line { stroke: #58a6ff; stroke-width: 2; fill: none; }")
    svg2 += f'  <text x="0" y="20" font-size="14" class="text">Activity</text>\n'
    
    # Simple line graph of weekly contributions
    weekly = [sum(days[i:i+7]) for i in range(0, len(days), 7)]
    max_weekly = max(weekly) if weekly else 1
    
    points = []
    for i, val in enumerate(weekly):
        x = (i / len(weekly)) * 620
        y = 140 - ((val / max_weekly) * 100)
        points.append(f"{x},{y}")
        
    pts_str = " ".join(points)
    svg2 += f'  <polyline points="{pts_str}" class="line"/>\n'
    # Add a little animation
    svg2 += f"""  <path d="M0,140 L{pts_str} L620,140 Z" fill="url(#grad)" opacity="0.2">
    <animate attributeName="opacity" values="0.1;0.3;0.1" dur="4s" repeatCount="indefinite" />
  </path>
  <defs>
    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{ACCENT_COLOR}"/>
      <stop offset="100%" stop-color="{ACCENT_COLOR}" stop-opacity="0"/>
    </linearGradient>
  </defs>"""
    svg2 += "</svg>"
    with open("../stats.svg", "w", encoding="utf-8") as f:
        f.write(svg2)

def generate_streak():
    print("Generating streak.svg...")
    font_b64 = subset_font("Streak 42 days (mock)")
    svg = get_base_svg(200, 150, font_b64)
    svg += '  <text x="100" y="50" font-size="14" class="text" text-anchor="middle">Current Streak</text>\n'
    svg += '  <text x="100" y="90" font-size="32" class="accent" text-anchor="middle" font-weight="bold">42</text>\n'
    svg += '  <text x="100" y="120" font-size="12" class="text" text-anchor="middle" opacity="0.7">days</text>\n'
    svg += "</svg>"
    with open("../streak.svg", "w", encoding="utf-8") as f:
        f.write(svg)

def generate_langs():
    print("Generating langs.svg...")
    font_b64 = subset_font("Top Languages Python C++ Bash OSINT")
    svg = get_base_svg(200, 150, font_b64)
    svg += '  <text x="10" y="30" font-size="14" class="text">Top Languages</text>\n'
    
    langs = [("Python", 45), ("C++", 30), ("Bash", 15), ("Other", 10)]
    y = 60
    for name, pct in langs:
        svg += f'  <text x="10" y="{y}" font-size="12" class="text">{name}</text>\n'
        svg += f'  <rect x="80" y="{y-10}" width="{pct}" height="10" fill="{ACCENT_COLOR}" rx="2"/>\n'
        svg += f'  <text x="{85+pct}" y="{y}" font-size="10" class="text" opacity="0.7">{pct}%</text>\n'
        y += 20
        
    svg += "</svg>"
    with open("../langs.svg", "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    download_font()
    
    generate_header("hd-about.svg", "Whoami")
    generate_header("hd-stack.svg", "Tech Stack")
    generate_header("hd-projects.svg", "Projects")
    generate_header("hd-stats.svg", "GitHub Stats")
    
    # The ascii takes a headshot in the root directory
    generate_ascii("../headshot.png")
    
    data = fetch_github_data()
    generate_stats_and_year(data)
    generate_streak()
    generate_langs()
    
    print("All SVGs generated successfully.")
