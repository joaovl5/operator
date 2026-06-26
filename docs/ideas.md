# Ideas

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
