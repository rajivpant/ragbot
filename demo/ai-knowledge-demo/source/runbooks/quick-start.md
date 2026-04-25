# Demo Quick Start

A short procedural runbook bundled with the demo.

## To kick the tires from the CLI

```bash
ragbot --demo                 # set demo mode for the whole session
ragbot db status              # show backend health and indexed collections
ragbot skills list            # show the bundled demo skill
ragbot chat -p "What is ragbot?" -profile demo
```

## To exit the demo cleanly

```bash
unset RAGBOT_DEMO
ragbot db status              # demo workspace can be cleared if you wish
ragbot skills index --workspace demo --force   # only if you want a fresh re-index
```

## To use this as a starting point for your own workspace

1. Copy `demo/ai-knowledge-demo/` to `~/workspaces/<you>/ai-knowledge-<you>/`.
2. Replace the markdown in `source/` with your own content.
3. Add the new repo to `~/.synthesis/console.yaml` so ragbot's discovery
   sees it without `RAGBOT_DEMO=1`.
