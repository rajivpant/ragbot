# Starter Template for Curated Datasets

This is a minimal starter template to help you get Ragbot up and running in minutes.

## What is this?

Curated datasets are files containing information that Ragbot will use as context when answering your questions. Think of it as giving Ragbot access to your personal knowledge base.

## How to use this template

1. **Copy this template to your data directory:**
   ```bash
   cp -r examples/datasets/starter-template/ datasets/my-data/
   ```

2. **Edit the files with your information:**
   - `about-me.md` - Basic personal information
   - `professional.md` - Work history and expertise
   - `preferences.md` - Communication style and interests

3. **Start Ragbot:**
   ```bash
   docker-compose up
   ```

## What to include

Good candidates for curated datasets:
- Personal background and bio
- Professional experience and skills
- Project documentation
- Research notes and references
- Writing style examples
- Contact information
- Family information (if you want AI to know about it)

## Privacy note

These files are stored locally and never uploaded anywhere unless you explicitly commit them to a git repository. By default, `datasets/` is in `.gitignore` to prevent accidental commits.

## Next steps

Once you're comfortable with the basics, explore:
- [Use case examples](../use-cases/) - See how others organize their data
- [Prompt library](../../prompt-library/) - Advanced prompting techniques
- [Custom instructions](../../instructions/) - Configure how Ragbot responds
