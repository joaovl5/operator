# Setting up `devenv`

1. **Install Nix:**
   - **Linux and MacOS:** `curl -sSfL https://artifacts.nixos.org/nix-installer | sh -s -- install --enable-flakes`
2. **For MacOS users:** MacOS ships an ancient version of bash due to
   licensing reasons, thus it's recommended to update it.
   - `nix profile add nixpkgs#bashInteractive`
3. **Install devenv:**
   - `nix profile add nixpkgs#devenv`
4. **To enter devenv shell:**
   - `devenv shell`
   - If you want to avoid using this command everytime, [you can setup
     auto-activation for your shell too.](https://devenv.sh/auto-activation/#setup)

> [!NOTE]
> We used `nix profile` commands for install examples since it's easier
> for beginners, but if you're already declaratively-installed packages
> in Nix (such as with home-manager, NixOS, nix-darwin, or others) you
> can safely use their alternative installation methods.
