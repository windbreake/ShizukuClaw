---
on:
  schedule: "0 3 * * *"  # 7 PM PST (3 AM UTC) daily
  workflow_dispatch:
permissions:
  contents: read
  issues: read
  pull-requests: read
network:
  allowed:
    - defaults
    - learn.microsoft.com
    - pypi.org
    - files.pythonhosted.org
tools:
  github:
  bash: ["python3", "pip", "git", "diff"]
safe-outputs:
  create-pull-request:
    title-prefix: "[docs-update] "
    labels: [automated, documentation]
---

# Update Foundry llms.txt Documentation

Regenerate the llms.txt and llms-full.txt files from the latest Microsoft Foundry documentation.

## Purpose

This workflow keeps our Foundry documentation index up-to-date by:
1. Fetching the latest Table of Contents from Microsoft Learn
2. Regenerating llms.txt with current documentation links
3. Creating a PR if there are changes

## Steps

1. **Setup Python environment**
   - Install required packages: `pip install aiohttp`

2. **Run the scraper**
   - Execute `python .github/scripts/scrape_foundry_docs.py` to regenerate llms.txt
   - Execute `python .github/scripts/generate_llms_full.py` to regenerate llms-full.txt

3. **Check for changes**
   - Compare the generated files with the existing ones
   - If there are changes, create a pull request with the updates

4. **Create PR if needed**
   - Title: "Update Foundry llms.txt documentation"
   - Include summary of what changed (new pages, removed pages, section changes)

## Notes

- The scraper respects rate limits when fetching from Microsoft Learn
- Only creates a PR if there are actual content changes
- The llms.txt follows the llms.txt specification for LLM-friendly documentation
