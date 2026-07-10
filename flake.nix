{
  description = "Operator - Operator - Operator";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    devenv = {
      url = "github:cachix/devenv";
      inputs = {
        flake-parts.follows = "flake-parts";
        nixpkgs.follows = "nixpkgs";
        nixd.inputs.treefmt-nix.follows = "treefmt-nix";
      };
    };
    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs = {nixpkgs.follows = "nixpkgs";};
  };

  outputs = {
    nixpkgs,
    flake-parts,
    devenv,
    ...
  } @ inputs:
    flake-parts.lib.mkFlake {inherit inputs;} {
      imports = [devenv.flakeModule];
      systems = nixpkgs.lib.systems.flakeExposed;
      perSystem = {pkgs, ...} @ args: {
        devenv.shells.default = {
          git-hooks = import ./nix/git-hooks.nix args;
          treefmt = {
            enable = true;
            config = import ./nix/treefmt.nix args;
          };
          packages = with pkgs; [
            just
            prek
          ];
        };
      };
    };
}
