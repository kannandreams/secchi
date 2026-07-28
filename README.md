# secchi

Beautiful TUI dashboard to monitor packages across PyPI, crates.io, and npm.

```bash
secchi --list
secchi -p tuffcli
secchi --config ./secchi.toml -p tuffcli
```

Secchi looks for config in this order: an explicit `--config` path,
`./secchi.toml`, legacy `./pkgwatch.toml`, then
`~/.config/secchi/config.toml`.
