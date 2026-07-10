{pkgs, ...} @ args: {
  git-hooks = import ./nix/git-hooks.nix args;
  treefmt = {
    enable = true;
    config = import ./nix/treefmt.nix args;
  };
  packages = with pkgs; [
    just
    prek
  ];
}
