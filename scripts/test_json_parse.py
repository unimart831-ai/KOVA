"""Test parse_llm_json with the exact content from the user's truncation report."""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"

from apps.agents.llm import parse_llm_json

# The EXACT content the user expected to see on LinkedIn
content = (
    "Stop buying social media tools. Start building a social media team.\n\n"
    "Here's the framework I use:\n\n"
    "The 3-Level Delegation Hierarchy for Founders:\n\n"
    "Level 1: Automate (The 'What')\n"
    "This is where most tools live. Scheduling. Basic analytics. "
    "They automate a single task. You're still the brain.\n\n"
    "Level 2: Delegate (The 'How')\n"
    "This is where you hand off a process. You define the outcome, "
    "and a system or person figures out the steps. You're the manager.\n\n"
    "Level 3: Own (The 'Why')\n"
    "This is strategy. Market positioning. Brand voice. "
    "The high-leverage decisions only you can make. You're the architect.\n\n"
    "Most founders get stuck at Level 1, automating tasks but never "
    "graduating to delegation.\n\n"
    "So we built Kova Agents not as a Level 1 tool, but as a Level 2 system.\n\n"
    "It\u2019s 6 specialized AI agents that operate as a team:\n\n"
    "1. Research Agent \u2192 Finds trends\n"
    "2. Create Agent \u2192 Writes content\n"
    "3. Analyst Agent \u2192 Predicts performance\n"
    "4. Adapt Agent \u2192 Tailors for each platform\n"
    "5. Engage Agent \u2192 Manages conversations\n"
    "6. Strategist Agent \u2192 Learns and recommends\n\n"
    "They run in a closed loop. Research informs Create. "
    "Analyst informs Adapt. Engage feeds back to Strategist.\n\n"
    "Your job shifts from operator to overseer. "
    "You own the 'Why' while the system handles the 'How'.\n\n"
    "The goal isn\u2019t to post faster. It\u2019s to think clearer.\n\n"
    "Question for my network: In your business, what\u2019s one process "
    "you\u2019ve successfully moved from Level 1 (Automate) to Level 2 "
    "(Delegate)? What changed?\n\n"
    "#FounderMindset #BusinessStrategy #AI #MarketingAutomation #Leadership"
)

print(f"Expected content length: {len(content)} chars")
print()

# === TEST 1: Properly escaped JSON (ideal case) ===
print("=" * 60)
print("TEST 1: Properly escaped JSON")
proper_json = json.dumps({
    "batch_strategy": "thought leadership",
    "posts": [{
        "platform": "linkedin",
        "content_text": content,
        "content_type": "thought_leadership",
        "image_prompt": "",
        "visual_strategy": {"strategy": "none"},
    }]
})
try:
    result = parse_llm_json(proper_json)
    parsed = result["posts"][0]["content_text"]
    print(f"  Parsed length: {len(parsed)}")
    print(f"  Match: {parsed == content}")
except Exception as e:
    print(f"  ERROR: {e}")

# === TEST 2: JSON with LITERAL newlines (common LLM failure) ===
print()
print("=" * 60)
print("TEST 2: JSON with LITERAL newlines")
bad_json = (
    '{"batch_strategy": "thought leadership", '
    '"posts": [{"platform": "linkedin", '
    '"content_text": "' + content + '", '
    '"content_type": "thought_leadership", '
    '"image_prompt": "", '
    '"visual_strategy": {"strategy": "none"}}]}'
)
try:
    result = parse_llm_json(bad_json)
    parsed = result["posts"][0]["content_text"]
    print(f"  Parsed length: {len(parsed)}")
    print(f"  Content preserved: {len(parsed) >= len(content) - 20}")
except Exception as e:
    print(f"  ERROR: {e}")

# === TEST 3: CRITICAL — Truncated JSON mid-content (simulates max_tokens hit) ===
print()
print("=" * 60)
print("TEST 3: Truncated JSON mid-content (max_tokens hit)")
# Build a properly escaped JSON, then truncate it mid-content_text
full_json = json.dumps({
    "batch_strategy": "thought leadership",
    "posts": [{
        "platform": "linkedin",
        "content_text": content,
        "content_type": "thought_leadership",
        "image_prompt": "",
        "visual_strategy": {"strategy": "none"},
    }, {
        "platform": "twitter",
        "content_text": "Short tweet version of the same idea",
        "content_type": "original",
    }]
})
# Truncate at various points to simulate token limit
for cut_at_text, label in [
    ("Level 1: Automate", "at 'Level 1: Automate'"),
    ("Level 2: Delegate", "at 'Level 2: Delegate'"),
    ("Research Agent", "at 'Research Agent'"),
]:
    # Find the position in the JSON and truncate there
    idx = full_json.find(cut_at_text)
    if idx == -1:
        # Try escaped version
        idx = full_json.find(cut_at_text.replace("'", "\\'"))
    if idx == -1:
        print(f"  [{label}] Could not find truncation point in JSON")
        continue
    truncated = full_json[:idx + len(cut_at_text)]
    try:
        result = parse_llm_json(truncated)
        posts = result.get("posts", [])
        if posts:
            parsed = posts[0].get("content_text", "")
            print(f"  [{label}] Parsed OK! content_text={len(parsed)} chars")
            print(f"    Ends with: {repr(parsed[-60:])}")
        else:
            print(f"  [{label}] Parsed but no posts found")
    except json.JSONDecodeError as e:
        print(f"  [{label}] FAILED to parse: {e}")

# === TEST 4: Multi-platform, twitter truncated (LinkedIn should survive) ===
print()
print("=" * 60)
print("TEST 4: Multi-platform, truncated in 2nd post (LinkedIn should survive)")
# Truncate in the middle of the twitter post
idx = full_json.find("Short tweet version")
if idx > 0:
    truncated = full_json[:idx + 10]  # "Short twee"
    try:
        result = parse_llm_json(truncated)
        posts = result.get("posts", [])
        print(f"  Posts found: {len(posts)}")
        for p in posts:
            plat = p.get("platform", "?")
            ct = p.get("content_text", "")
            print(f"    {plat}: {len(ct)} chars | ends: {repr(ct[-40:]) if ct else '<empty>'}")
    except json.JSONDecodeError as e:
        print(f"  FAILED to parse: {e}")
