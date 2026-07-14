# Ideas

## For core

### Data Modeling

- A `SessionAgent` can contain a list of ongoing jobs, which are
  commands that may be background/foreground objects.
- Keep track of ongoing jobs on the database as well, avoid having
  state outside the database for long - this will benefit from having
  detections of job interruptions as well.
- Global server lock that requires constant refreshes:
  - on some known file `PATH.lock`
  - lockfile contents must contain 'heartbeat' timestamp that is to
    occur every N minutes (e.g. every 5 minutes), as well as a unique
    per-execution ID (just a random number)
  - other processes will know the lock should be released if heartbeat
    is older than N
  - in case the process halted and comes back, it should check if
    heartbeat was acquired by any other process by checking if the
    per-execution ID has changed

### Data Communication

- Have sort of API via unix socket or `127.0.0.1`

### Agent

#### Extras

- External environment control tooling, let agent handle commands on
  some environment, either tmux, a container, or a VM, having text or
  graphical views
- Code metadata -- have commits and diffs tagged with
  session+epoch+event IDs for tracking reasoning - may be via:
  - inline/in-file via code comments
  - separate tracking file `.operator/` made alongside
  - commit metadata

#### Experiments

- Codebase context representation
  - Via AST+LSP analysis
  - Summary presentation via rendered diagram image
  - Constant guidance via system hints when handling relevant files
  - Rules system via regexes and other triggers

  ```markdown
  ---
  name: writing-tests
  triggers:
    glob: << **/*.test.py
    regex: << "test_\w+"
    imports: << pytest # lsp-aware stuff
  ---
  ```

## For TUI/Interface

- Have modal-based interaction:
  - normal mode for navigating in input and messages
  - insert mode for writing, like vim
  - insert mode should be able to be used on its own if some prefer it,
    and other modes may be disabled to be more approachable
- Allow navigating between agent tree/graph - either running or
  terminated agents
  - Visualization of graph (unicode/kitty-image)

Technical/lower-level:

- Have server/daemon-client (client being TUI/...) flow so that
  footprint is reduced and no state problems happen
- Framework allowing TUI to be also handled as a web-ui and possibly
  other UI types (maybe Emacs buffer/window or android app)
