{pkgs, ...}: {
  src = ../.;
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

    treefmt = {
      enable = true;
      name = "treefmt";
      entry = "treefmt";
      pass_filenames = true;
      language = "unsupported";
    };
  };
}
