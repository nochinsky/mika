#!/usr/bin/env bash
# Per-user Linux/WSL installer. No sudo, compiler, microphone access, or model download.
set -euo pipefail

fail() { printf 'mika: %s\n' "$*" >&2; exit 1; }
command -v uname >/dev/null || fail 'uname is required.'
[[ $(uname -s) == Linux ]] || fail 'This installer supports Linux/WSL. Use install.ps1 on Windows.'
[[ $(uname -m) == x86_64 ]] || fail 'Prebuilt releases currently support x86-64 only.'
[[ ${EUID:-$(id -u)} != 0 ]] || fail 'Run this as your normal user, without sudo.'
[[ ${HOME:-} == /* && $HOME != / ]] || fail 'An absolute, non-root HOME directory is required.'
for tool in curl tar sha256sum mktemp grep readlink; do
    command -v "$tool" >/dev/null || fail "$tool is required."
done

version=${MIKA_VERSION:-latest}
[[ $version =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail 'Invalid MIKA_VERSION.'
asset=mika-linux-x86_64.tar.gz
base=https://github.com/nochinsky/mika/releases
if [[ $version == latest ]]; then base+=/latest/download; else base+=/download/"$version"; fi

data=${XDG_DATA_HOME:-$HOME/.local/share}
[[ $data == /* ]] || data=$HOME/.local/share
parent=$data/mika
root=$parent/app
bin=$HOME/.local/bin
[[ ! -e $root || -f $root/VERSION ]] || fail "Refusing to replace an unrelated directory: $root"
if [[ -e $bin/mika || -L $bin/mika ]]; then
    [[ -L $bin/mika && $(readlink "$bin/mika") == "$root/bin/mika" ]] ||
        fail "An unrelated $bin/mika already exists. Move it aside first."
fi
mkdir -p "$parent" "$bin"
work=$(mktemp -d "$parent/.install.XXXXXXXX")
backup=$work/previous-app
installed=0
success=0
cleanup() {
    local status=$?
    if (( !success )); then
        if (( installed )); then rm -rf -- "$root"; fi
        if [[ -e $backup || -L $backup ]]; then mv -- "$backup" "$root"; fi
    fi
    rm -rf -- "$work"
    return "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

printf 'Installing Mika (%s) for Linux/WSL...\n' "$version"
if [[ -n ${MIKA_ARCHIVE_PATH:-} ]]; then
    cp -- "$MIKA_ARCHIVE_PATH" "$work/$asset"
    cp -- "$MIKA_ARCHIVE_PATH.sha256" "$work/$asset.sha256"
else
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 30 --max-time 600 --max-filesize 268435456 \
        "$base/$asset" --output "$work/$asset"
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 30 --max-time 60 --max-filesize 4096 \
        "$base/$asset.sha256" --output "$work/$asset.sha256"
fi
read -r expected _ < "$work/$asset.sha256"
[[ $expected =~ ^[0-9a-fA-F]{64}$ ]] || fail 'Invalid release checksum file.'
(cd "$work" && printf '%s  %s\n' "$expected" "$asset" | sha256sum --check --status) ||
    fail 'Release checksum mismatch. Nothing was installed.'
# Extract only the expected package layout, never absolute/parent-relative paths.
while IFS= read -r entry; do
    [[ $entry == mika/* && $entry != *'/../'* && $entry != */.. ]] || fail 'Unsafe archive path.'
done < <(tar -tzf "$work/$asset")
tar -xzf "$work/$asset" --no-same-owner --no-same-permissions -C "$work"
candidate=$work/mika
[[ -f $candidate/VERSION && -x $candidate/bin/mika ]] || fail 'Incomplete release package.'
"$candidate/bin/mika" --version || fail 'This binary cannot run here. Linux glibc 2.35+ is required.'
if [[ -e $root || -L $root ]]; then mv -- "$root" "$backup"; fi
mv -- "$candidate" "$root"
installed=1
"$root/bin/mika" --version >/dev/null || fail 'Installed binary failed its startup check.'
ln -sfn -- "$root/bin/mika" "$bin/mika"
success=1

# A piped child shell cannot change its parent's PATH. Configure future shells,
# and print the exact command to activate it in the current one.
path_block='# >>> Mika CLI >>>
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
# <<< Mika CLI <<<'
add_profile() {
    local file=$1
    if ! grep -Fq '# >>> Mika CLI >>>' "$file" 2>/dev/null; then
        if ! printf '\n%s\n' "$path_block" >> "$file"; then
            printf 'Warning: could not update %s; add ~/.local/bin to PATH manually.\n' "$file" >&2
        fi
    fi
}
shell_name=${SHELL:-/bin/bash}
case ${shell_name##*/} in
    zsh) add_profile "${ZDOTDIR:-$HOME}/.zshrc" ;;
    fish)
        fish_dir=${XDG_CONFIG_HOME:-$HOME/.config}/fish/conf.d
        if mkdir -p "$fish_dir"; then
            if [[ ! -e $fish_dir/mika.fish ]]; then
                printf '%s\n' 'fish_add_path --path "$HOME/.local/bin"' > "$fish_dir/mika.fish" || true
            fi
        fi ;;
    *) add_profile "$HOME/.bashrc"; add_profile "$HOME/.profile" ;;
esac
printf '\nMika installed: %s/mika\n' "$bin"
case ":${PATH:-}:" in
    *":$bin:"*) printf 'Run: mika\n' ;;
    *) printf 'Restart your terminal, or run now: %q\n' "$bin/mika"
       printf 'For bash/zsh, activate PATH now: export PATH="$HOME/.local/bin:$PATH"\n' ;;
esac
printf 'On first run, Mika asks before downloading its 279 MB model. No audio was recorded.\n'
