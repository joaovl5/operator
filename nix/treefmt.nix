_: {
  projectRootFile = "flake.nix";

  programs = {
    # nix
    alejandra.enable = true;
    deadnix.enable = true;
    statix.enable = true;
    flake-edit.enable = true;
    # toml
    taplo.enable = true;
    # md
    prettier.enable = true;
  };
}
