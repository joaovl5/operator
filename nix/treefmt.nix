_: {
  projectRootFile = "devenv.nix";

  programs = {
    # nix
    alejandra.enable = true;
    deadnix.enable = true;
    statix.enable = true;
    # toml
    taplo.enable = true;
    # md
    prettier.enable = true;
  };
}
