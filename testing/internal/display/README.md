# Live test display

Compiler-owned Ocean frontend for `ocean test`, implemented with the standard
`term/tui` Model/Update/View and command APIs. It runs separately from tests so
stdout, panics, and fatal failures cannot disturb terminal rendering.

The compiler provides a private event descriptor and command arguments. Run it
through `ocean test`; its transport and model are internal implementation details.
The frontend handles running/completed tests and subtests, logs, status counts,
elapsed time, window resizing, scrolling, following, and Ctrl+C/q cancellation.
The compiler retains JSON/file reporting, process status, signals, and timeouts.

Model tests can run without a terminal:

```sh
OCEAN_SRC=/path/to/ocean-src ocean test /path/to/ocean-src/testing/internal/display --notty
```

The compiler's `tests/ocean_test_tui_test.py` tests the complete PTY integration.
