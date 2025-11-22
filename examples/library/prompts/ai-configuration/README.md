# AI Configuration

System-level instructions that configure how AI assistants should behave, generate content, and process information.

## Purpose

This folder contains prompts that establish fundamental behaviors and constraints for AI systems. These are typically used as:
- Custom instructions in Claude Projects
- System prompts in API implementations
- Configuration files for AI applications
- Foundational rules that apply across multiple use cases

## Contents

### Anti-Watermarking Instructions for AI Text Generation.md
Requests that AI-generated text not include watermarks, invisible characters, or statistical patterns that identify content as AI-generated. Establishes principles around content ownership and privacy.

**Use when:** Configuring any AI system for text generation where you want clean, unmodified output.

### code-generation-and-editing.md
Structured approach for AI to generate code solutions. Requires the AI to:
1. Analyze the task and existing code
2. Generate multiple distinct approaches
3. Evaluate pros/cons of each approach
4. Select and justify the optimal solution
5. Implement with clear documentation

**Use when:** Requesting code modifications or new implementations where you want multiple options evaluated.

### combine-ragbot-responses.md
Instructions for merging multiple LLM responses into a single, comprehensive document without losing detail. Emphasizes that the combined version should be more detailed than any individual response.

**Use when:** You have responses from multiple AI systems (or multiple runs) and want to create a unified, comprehensive output.

## Usage Guidelines

**Platform-Specific Implementation:**
- **Claude Projects:** Add these files to Project Knowledge or incorporate into Custom Instructions
- **ChatGPT:** Adapt content for Custom Instructions (note character limits)
- **API Usage:** Include as system messages or configuration parameters

**Combining Multiple Configurations:**
You can use multiple files from this folder together, but ensure they don't contain conflicting instructions.

## Maintenance Notes

These files establish foundational behavior. Changes here affect all work using these configurations, so:
- Test changes thoroughly before committing
- Document the rationale for any modifications
- Consider version control for significant changes
