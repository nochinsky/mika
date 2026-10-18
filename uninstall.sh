#!/usr/bin/env bash
# Per-user Linux/WSL removal. Never run with sudo; never follows an app/cache link.
set -euo pipefail

fail() { printf 'mika: %s\n' "$*" >&2; exit 1; }
warn() { printf 'mika: %s\n' "$*" >&2; }
[[ $(uname -s) == Linux ]] || fail 'Use uninstall.ps1 on Windows.'
[[ ${EUID:-$(id -u)} != 0 ]] || fail 'Run this as your normal user, without sudo.'
[[ ${HOME:-} == /* && $HOME != / ]] || fail 'An absolute, non-root HOME directory is required.'
for tool in flock readlink mktemp chmod cmp mv rm rmdir; do
    command -v "$tool" >/dev/null || fail "$tool is required."
done
keep=${MIKA_KEEP_MODEL:-0}
yes=${MIKA_UNINSTALL_YES:-0}
while (( $# )); do
    case $1 in
        --keep-model) keep=1 ;;
        --yes) yes=1 ;;
        --help|-h)
            printf '%s\n' 'Usage: bash uninstall.sh [--keep-model] [--yes]' \
                'Removes the installer-managed app, cached speech model, and Mika shell setup.' \
                'MIKA_KEEP_MODEL=1 preserves speech weights; MIKA_UNINSTALL_YES=1 skips confirmation.'
            exit 0 ;;
        *) fail "Unknown argument: $1" ;;
    esac
    shift
done
[[ $keep == 0 || $keep == 1 ]] || fail 'MIKA_KEEP_MODEL must be 0 or 1.'
[[ $yes == 0 || $yes == 1 ]] || fail 'MIKA_UNINSTALL_YES must be 0 or 1.'
data=${XDG_DATA_HOME:-$HOME/.local/share}
[[ $data == /* ]] || data=$HOME/.local/share
parent=$data/mika
root=$parent/app
models=$parent/models
command_path=$HOME/.local/bin/mika
model=granite-speech-5.0-470m-turboctc-Q4_K_M.gguf

validate() {
    local path version fingerprint
    for path in "$parent" "$root" "$models"; do
        [[ ! -L $path ]] || fail "Refusing a linked application/data directory: $path"
        [[ ! -e $path || -d $path ]] || fail "Expected a directory: $path"
    done
    if [[ -d $root ]]; then
        for path in "$root/VERSION" "$root/ARCHIVE_SHA256"; do
            [[ -f $path && ! -L $path ]] || fail "Not an installer-managed app; refusing to remove $root"
        done
        version=$(<"$root/VERSION")
        fingerprint=$(<"$root/ARCHIVE_SHA256")
        [[ $version =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ && $fingerprint =~ ^[0-9a-fA-F]{64}$ ]] ||
            fail "Invalid installation markers; refusing to remove $root"
    fi
    for path in "$parent/.installer.lock" "$models/.download.lock"; do
        [[ ! -L $path && ( ! -e $path || -f $path ) ]] || fail "Unsafe lock file: $path"
    done
    if [[ $keep == 0 ]]; then
        shopt -s nullglob
        for path in "$models/$model" "$models/$model".part.*; do
            [[ ! -e $path || -f $path || -L $path ]] || fail "Not a model file: $path"
        done
        shopt -u nullglob
    fi
}
check_running() {
    local executable target expected
    expected=$(readlink -m -- "$root/bin/mika")
    for executable in /proc/[0-9]*/exe; do
        target=$(readlink -- "$executable" 2>/dev/null) || continue
        [[ $target != "$expected" ]] || fail 'Mika is running. Close Mika and try again.'
    done
}
validate
check_running
printf 'Mika will remove:\n  App: %s\n' "$root"
if [[ $keep == 0 ]]; then
    printf '  Cached speech model and its partial downloads: %s\n' "$models"
else
    printf '  Speech model will be kept: %s\n' "$models"
fi
printf '  Mika command link and unchanged installer-created shell setup.\n'
printf 'Unrelated files, source builds, and notes outside the app are kept. Close Mika first.\n'
if [[ $yes == 0 ]]; then
    # stdin can contain the rest of curl's script: consent must come from /dev/tty.
    if ! { exec 7<>/dev/tty; } 2>/dev/null; then
        fail 'No interactive terminal; no changes made. Use --yes only for deliberate unattended removal.'
    fi
    printf 'Remove Mika? [y/N] ' >&7
    answer=''
    if ! IFS= read -r answer <&7 || [[ $answer != y && $answer != Y && $answer != yes && $answer != YES ]]; then
        printf 'Cancelled; no changes made.\n'
        exit 130
    fi
    exec 7>&-
fi
trap 'exit 130' INT TERM
# Do not create directories on an already-uninstalled machine.
if [[ -d $parent ]]; then
    exec 9>>"$parent/.installer.lock"
    flock -n 9 || fail 'Another Mika installer/uninstaller is running. Try again later.'
fi
if [[ -d $models ]]; then
    exec 8>>"$models/.download.lock"
    flock -n 8 || fail 'A Mika model download is running. Close Mika and try again.'
fi
validate
check_running

path_block='# >>> Mika CLI >>>
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
# <<< Mika CLI <<<'
profile_temp=''
trap '[[ -z $profile_temp ]] || rm -f -- "$profile_temp"' EXIT
clean_profile() {
    local file=$1 content='' cleaned
    [[ -e $file || -L $file ]] || return 0
    if [[ -L $file || ! -f $file || ! -r $file ]]; then
        warn "Leaving linked/unreadable shell profile unchanged: $file"
        return 0
    fi
    # Bash read preserves all trailing newlines; reject embedded NULs.
    if IFS= read -r -d '' content < "$file"; then
        warn "Leaving a shell profile containing NUL bytes unchanged: $file"
        return 0
    fi
    cleaned=$'\n'$content
    cleaned=${cleaned//$'\n'"$path_block"$'\n'/$'\n'}
    cleaned=${cleaned:1}
    if [[ $cleaned == "$content" ]]; then
        [[ $content != *'# >>> Mika CLI >>>'* ]] || warn "Leaving customized Mika shell setup unchanged: $file"
        return 0
    fi
    profile_temp=$(mktemp "${file}.mika-uninstall.XXXXXXXX")
    printf '%s' "$cleaned" > "$profile_temp"
    chmod --reference="$file" "$profile_temp"
    mv -f -- "$profile_temp" "$file"
    profile_temp=''
    [[ $cleaned != *'# >>> Mika CLI >>>'* ]] || warn "Customized Mika shell setup remains in $file"
    return 0
}
# Clean the supported profiles even if the user's current shell has changed.
for profile in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc" "${ZDOTDIR:-$HOME}/.zshrc"; do
    clean_profile "$profile"
done
for config in "$HOME/.config" "${XDG_CONFIG_HOME:-$HOME/.config}"; do
    fish=$config/fish/conf.d/mika.fish
    [[ -f $fish && ! -L $fish ]] || continue
    content=''
    if ! IFS= read -r -d '' content < "$fish" && [[ $content == 'fish_add_path --path "$HOME/.local/bin"'$'\n' ]]; then
        rm -f -- "$fish"
    else
        warn "Leaving customized Mika Fish setup unchanged: $fish"
    fi
done
if [[ -L $command_path ]]; then
    target=$(readlink -- "$command_path")
    [[ $target == /* ]] || target=${command_path%/*}/$target
    if [[ $(readlink -m -- "$target") == "$(readlink -m -- "$root/bin/mika")" ]]; then
        rm -- "$command_path"
    else
        warn "Leaving an unrelated command unchanged: $command_path"
    fi
elif [[ -e $command_path ]]; then
    warn "Leaving an unrelated/source-build command unchanged: $command_path"
fi
if [[ -d $root ]]; then
    # Keep ownership markers while removing payloads, so ordinary interruptions
    # can be retried without misidentifying the remaining app as unrelated.
    shopt -s nullglob dotglob
    for entry in "$root"/*; do
        case ${entry##*/} in VERSION|ARCHIVE_SHA256) continue ;; esac
        rm -rf -- "$entry"
    done
    shopt -u nullglob dotglob
    rm -f -- "$root/VERSION" "$root/ARCHIVE_SHA256"
    rmdir -- "$root"
fi
if [[ $keep == 0 && -d $models ]]; then
    shopt -s nullglob
    rm -f -- "$models/$model" "$models/$model".part.*
    shopt -u nullglob
fi
# Remove coordination files last. Retain the installer lock if unrelated data or
# preserved models remain, so concurrent installers still share the same inode.
if [[ -d $models ]]; then
    rm -f -- "$models/.download.lock"
    rmdir -- "$models" 2>/dev/null || true
fi
if [[ -d $parent ]]; then
    shopt -s nullglob dotglob
    remaining=("$parent"/*)
    shopt -u nullglob dotglob
    if (( ${#remaining[@]} == 1 )) && [[ ${remaining[0]} == "$parent/.installer.lock" ]]; then
        rm -f -- "$parent/.installer.lock"
        rmdir -- "$parent" 2>/dev/null || true
    else
        warn "Retained models, unrelated files or recovery directories remain in $parent"
    fi
fi
printf 'Mika uninstalled. Restart your terminal to refresh command lookup.\n'
