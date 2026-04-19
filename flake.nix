{
  description = "Operator - Operator - Operator";

  inputs = {
    # nix
    ## pkgs
    nixpkgs.url = "git+https://github.com/NixOS/nixpkgs?ref=nixos-unstable&shallow=1";
    ## systems
    all-systems = {
      url = "git+ssh://git@github.com/nix-systems/default.git?shallow=1";
    };
    ## utils
    flake-utils = {
      url = "git+ssh://git@github.com/numtide/flake-utils.git?shallow=1";
    };
    treefmt-nix = {
      url = "git+ssh://git@github.com/numtide/treefmt-nix.git?shallow=1";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    git-hooks = {
      url = "git+ssh://git@github.com/cachix/git-hooks.nix?shallow=1";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    treefmt-nix,
    git-hooks,
    ...
  }: let
    flib = flake-utils.lib;
  in
    flib.eachDefaultSystem (system: let
      pkgs = import nixpkgs {inherit system;};
      treefmt_eval = treefmt-nix.lib.evalModule pkgs ./treefmt.nix;
      treefmt = treefmt_eval.config.build;
      git_hooks_lib = git-hooks.lib.${system};
      git_hook = git_hooks_lib.run (import ./git-hooks.nix pkgs);
    in {
      formatter = treefmt.wrapper;
      checks = {
        formatting = treefmt.check self;
      };

      devShells.default = pkgs.mkShell {
        inherit (git_hook) shellHook;
        buildInputs = git_hook.enabledPackages;

        packages = with pkgs; [
          just
          mdbook
          prek
        ];
      };
    });
}
