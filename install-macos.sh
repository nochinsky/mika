#!/bin/bash
# Experimental Apple Silicon/macOS 14+ installer. CPU-only, per-user, no Homebrew.
set -euo pipefail
fail() { printf 'mika: %s\n' "$*" >&2; exit 1; }
[[ $(uname -s) == Darwin ]] || fail 'This installer is for macOS; use install.sh on Linux.'
[[ $(uname -m) == arm64 ]] || fail 'Experimental Mac builds require native Apple Silicon (not Intel/Rosetta).'
[[ $(sw_vers -productVersion) =~ ^([0-9]+)\. && ${BASH_REMATCH[1]} -ge 14 ]] || fail 'macOS 14 or newer is required.'
[[ $(id -u) != 0 ]] || fail 'Run as your normal user, without sudo.'
[[ ${HOME:-} == /* && $HOME != / ]] || fail 'An absolute, non-root HOME is required.'
for tool in curl tar shasum mktemp grep readlink tr lsof; do
    command -v "$tool" >/dev/null || fail "$tool is required."
done
version=${MIKA_VERSION:-latest}
reinstall=${MIKA_REINSTALL:-0}
[[ $version =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail 'Invalid MIKA_VERSION.'
[[ $reinstall == 0 || $reinstall == 1 ]] || fail 'MIKA_REINSTALL must be 0 or 1.'
parent=$HOME/Library/Application\ Support/Mika
root=$parent/app
bin=$HOME/.local/bin
lock=$parent/.maintenance-lock
for path in "$parent" "$root"; do
    [[ ! -L $path && ( ! -e $path || -d $path ) ]] || fail "Unsafe application directory: $path"
done
mkdir -p "$parent" "$bin"
# mkdir is atomic and available in stock macOS; do not depend on GNU flock.
mkdir "$lock" 2>/dev/null || fail "Another installer/uninstaller is active. If none is running, inspect/remove $lock"
work=''
backup=''
installed=0
success=0
cleanup() {
    local status=$?
    if (( !success )) && [[ -n $work ]]; then
        if (( installed )) || [[ -e $backup ]]; then
            if ! rm -rf "$root"; then
                printf 'mika: recovery retained at %s\n' "$work" >&2
                rmdir "$lock" 2>/dev/null || true
                return 1
            fi
        fi
        if [[ -e $backup ]] && ! mv "$backup" "$root"; then
            printf 'mika: previous app retained at %s\n' "$backup" >&2
            rmdir "$lock" 2>/dev/null || true
            return 1
        fi
    fi
    [[ -z $work ]] || rm -rf "$work"
    rmdir "$lock" 2>/dev/null || true
    return "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
[[ ! -e $root || ( -f $root/VERSION && ! -L $root/VERSION && -f $root/ARCHIVE_SHA256 && ! -L $root/ARCHIVE_SHA256 ) ]] ||
    fail "Refusing an unrelated app directory: $root"
if [[ -e $bin/mika || -L $bin/mika ]]; then
    [[ -L $bin/mika && $(readlink "$bin/mika") == "$root/bin/mika" ]] || fail "Unrelated command exists: $bin/mika"
fi
if [[ -f $root/bin/mika ]] && lsof -t "$root/bin/mika" >/dev/null 2>&1; then
    fail 'Close Mika before updating.'
fi
asset=mika-macos-arm64.tar.gz
base=https://github.com/nochinsky/mika/releases
if [[ $version == latest ]]; then base=$base/latest/download; else base=$base/download/$version; fi
work=$(mktemp -d "$parent/.install.XXXXXXXX")
backup=$work/previous-app
fetch() {
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 30 --max-time "$3" --max-filesize "$4" "$1" --output "$2"
}
printf 'Checking experimental Mika CPU build for macOS...\n'
if [[ -n ${MIKA_ARCHIVE_PATH:-} ]]; then cp "$MIKA_ARCHIVE_PATH.sha256" "$work/checksum"
else fetch "$base/$asset.sha256" "$work/checksum" 60 4096; fi
read -r expected _ < "$work/checksum"
[[ $expected =~ ^[a-fA-F0-9]{64}$ ]] || fail 'Invalid release checksum.'
expected=$(printf '%s' "$expected" | tr '[:upper:]' '[:lower:]')
current=0
old_version=''
[[ ! -f $root/VERSION ]] || old_version=$(<"$root/VERSION")
if [[ $reinstall == 0 && -f $root/ARCHIVE_SHA256 && -x $root/bin/mika && $(<"$root/ARCHIVE_SHA256") == "$expected" ]]; then
    if actual=$("$root/bin/mika" --version 2>/dev/null) && [[ $actual == "mika ${old_version#v}" ]]; then current=1; fi
fi
if (( current )); then
    message="Mika ${old_version#v} is already up to date."
else
    if [[ -n ${MIKA_ARCHIVE_PATH:-} ]]; then cp "$MIKA_ARCHIVE_PATH" "$work/$asset"
    else fetch "$base/$asset" "$work/$asset" 600 268435456; fi
    read -r actual _ < <(shasum -a 256 "$work/$asset")
    [[ $actual == "$expected" ]] || fail 'Checksum mismatch; existing installation unchanged.'
    entries=$(tar -tzf "$work/$asset") || fail 'Invalid archive.'
    while IFS= read -r entry; do
        [[ $entry == mika/* && $entry != *'/../'* && $entry != */.. ]] || fail 'Unsafe archive path.'
    done <<< "$entries"
    # The static ARM64 package needs no symlinks/hardlinks/special files.
    listing=$(tar -tvzf "$work/$asset") || fail 'Invalid archive.'
    while IFS= read -r entry; do
        case $entry in d*|-*) ;; *) fail 'Archive contains a link or special file.' ;; esac
    done <<< "$listing"
    tar -xzf "$work/$asset" --no-same-owner -C "$work"
    candidate=$work/mika
    [[ -f $candidate/VERSION && -x $candidate/bin/mika ]] || fail 'Incomplete package.'
    candidate_version=$(<"$candidate/VERSION")
    [[ $candidate_version =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail 'Invalid package version.'
    actual=$("$candidate/bin/mika" --version) || fail 'Binary cannot start on this Mac.'
    [[ $actual == "mika ${candidate_version#v}" ]] || fail 'Binary/package version mismatch.'
    printf '%s\n' "$expected" > "$candidate/ARCHIVE_SHA256"
    [[ ! -e $root ]] || mv "$root" "$backup"
    installed=1
    mv "$candidate" "$root"
    "$root/bin/mika" --version >/dev/null || fail 'Installed startup check failed.'
    message="Installed Mika ${candidate_version#v} (experimental macOS CPU build)."
fi
ln -sfn "$root/bin/mika" "$bin/mika"
success=1
path_block='# >>> Mika CLI >>>
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
# <<< Mika CLI <<<'
add_profile() {
    if ! grep -Fq '# >>> Mika CLI >>>' "$1" 2>/dev/null; then
        printf '\n%s\n' "$path_block" >> "$1" || printf 'mika: configure PATH manually in %s\n' "$1" >&2
    fi
}
shell_name=${SHELL:-/bin/zsh}
case ${shell_name##*/} in
    zsh) add_profile "${ZDOTDIR:-$HOME}/.zshrc" ;;
    fish)
        config=${XDG_CONFIG_HOME:-$HOME/.config}/fish/conf.d
        mkdir -p "$config"
        [[ -e $config/mika.fish ]] || printf '%s\n' 'fish_add_path --path "$HOME/.local/bin"' > "$config/mika.fish" ;;
    *) add_profile "$HOME/.bashrc"; add_profile "$HOME/.profile" ;;
esac
printf '%s\nRestart your terminal, then run: mika\n' "$message"
printf 'Microphone permissions/capture are experimental and need real-Mac testing.\n'
