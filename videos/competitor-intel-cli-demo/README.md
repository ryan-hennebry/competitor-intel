# CLI Demo Video (Remotion)

This folder renders the terminal animation used in the `competitor-intel` README.

## Quick start

```bash
cd videos/competitor-intel-cli-demo
npm install
npm run dev
```

Open Remotion Studio and preview the `CliDemo` composition.

## Render

```bash
cd videos/competitor-intel-cli-demo
npm run render:cli
```

Output:

- `out/cli-demo.mp4`

## Customize the script

Edit `src/cliDemoData.ts`:

- change lines in `CLI_LINES`
- adjust `start` frame values for pacing
- tune `typingSpeed` for command typing feel
