pkgs: {
  src = ./.;
  package = pkgs.prek;

  hooks = {
    trim-trailing-whitespace.enable = true;
    check-merge-conflicts.enable = true;
    detect-private-keys.enable = true;
    mixed-line-endings.enable = true;
    fix-byte-order-marker.enable = true;
    check-toml.enable = true;
    check-yaml.enable = true;
    check-added-large-files = {
      enable = true;
      args = ["--maxkb=50000"];
    };
    treefmt_nix = {
      enable = true;
      name = "treefmt_nix";
      entry = "nix fmt";
      pass_filenames = true;
      language = "unsupported";
    };
    nix_flake_check = {
      enable = true;
      name = "nix_flake_check";
      entry = "nix flake check";
      pass_filenames = false;
      stages = ["pre-push"];
    };
  };
}
