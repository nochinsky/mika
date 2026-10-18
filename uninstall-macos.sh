#!/bin/bash
# Experimental macOS removal, compatible with the system Bash 3.2 and BSD tools.
set -euo pipefail
fail() { printf 'mika: %s\n' "$*" >&2; exit 1; }
warn() { printf 'mika: %s\n' "$*" >&2; }
[[ $(uname -s) == Darwin ]] || fail 'This script is for macOS; use uninstall.sh on Linux.'
[[ $(id -u) != 0 ]] || fail 'Run as your normal user, without sudo.'
[[ ${HOME:-} == /* && $HOME != / ]] || fail 'An absolute, non-root HOME is required.'
for tool in lsof readlink mktemp stat chmod mv rm rmdir; do command -v "$tool" >/dev/null || fail "$tool is required."; done
keep=${MIKA_KEEP_MODEL:-0}
yes=${MIKA_UNINSTALL_YES:-0}
while (( $# )); do
    case $1 in
        --keep-model) keep=1 ;; --yes) yes=1 ;;
        --help|-h) printf '%s\n' 'Usage: bash uninstall-macos.sh [--keep-model] [--yes]'; exit 0 ;;
        *) fail "Unknown argument: $1" ;;
    esac
    shift
done
[[ $keep == 0 || $keep == 1 ]] || fail 'MIKA_KEEP_MODEL must be 0 or 1.'
[[ $yes == 0 || $yes == 1 ]] || fail 'MIKA_UNINSTALL_YES must be 0 or 1.'
parent=$HOME/Library/Application\ Support/Mika
root=$parent/app
models=$parent/models
lock=$parent/.maintenance-lock
model=granite-speech-5.0-470m-turboctc-Q4_K_M.gguf
validate() {
    local path version hash
    for path in "$parent" "$root" "$models"; do
        [[ ! -L $path && ( ! -e $path || -d $path ) ]] || fail "Unsafe application/data directory: $path"
    done
    if [[ -d $root ]]; then
        for path in "$root/VERSION" "$root/ARCHIVE_SHA256"; do
            [[ -f $path && ! -L $path ]] || fail "Not an installer-managed app: $root"
        done
        version=$(<"$root/VERSION")
        hash=$(<"$root/ARCHIVE_SHA256")
        [[ $version =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ && $hash =~ ^[a-fA-F0-9]{64}$ ]] || fail 'Invalid ownership markers.'
    fi
    [[ ! -L $models/.download.lock && ( ! -e $models/.download.lock || -f $models/.download.lock ) ]] || fail 'Unsafe model lock.'
    shopt -s nullglob
    for path in "$models/$model" "$models/$model".part.*; do
        [[ ! -e $path || -f $path || -L $path ]] || fail "Not a model file: $path"
    done
    shopt -u nullglob
}
check_active() {
    local path
    for path in "$root/bin/mika" "$models/$model" "$models/.download.lock"; do
        if [[ -f $path ]] && lsof -t "$path" >/dev/null 2>&1; then
            fail 'Mika or a model download is active. Close Mika and try again.'
        fi
    done
}
validate
check_active
printf 'Mika will remove:\n  App: %s\n' "$root"
if [[ $keep == 0 ]]; then printf '  Fixed speech weights and partial downloads: %s\n' "$models"
else printf '  Speech model will be kept: %s\n' "$models"; fi
printf '  Mika command link and unchanged shell setup. Notes outside the app are kept.\n'
if [[ $yes == 0 ]]; then
    if ! { exec 7<>/dev/tty; } 2>/dev/null; then fail 'No controlling terminal; use --yes only for deliberate unattended removal.'; fi
    printf 'Remove Mika? [y/N] ' >&7
    answer=''
    if ! IFS= read -r answer <&7 || [[ $answer != y && $answer != Y && $answer != yes && $answer != YES ]]; then
        printf 'Cancelled; no changes made.\n'
        exit 130
    fi
    exec 7>&-
fi
locked=0
temporary=''
cleanup() {
    [[ -z $temporary ]] || rm -f "$temporary"
    if (( locked )); then rmdir "$lock" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM
if [[ -d $parent ]]; then
    mkdir "$lock" 2>/dev/null || fail "Another installer/uninstaller is active. If none is running, inspect/remove $lock"
    locked=1
fi
validate
check_active
path_block='# >>> Mika CLI >>>
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
# <<< Mika CLI <<<'
clean_profile() {
    local file=$1 content='' cleaned mode
    [[ -e $file || -L $file ]] || return 0
    if [[ -L $file || ! -f $file || ! -r $file ]]; then warn "Profile retained for manual cleanup: $file"; return 0; fi
    if IFS= read -r -d '' content < "$file"; then warn "Profile with NUL bytes retained: $file"; return 0; fi
    cleaned=$'\n'$content
    cleaned=${cleaned//$'\n'"$path_block"$'\n'/$'\n'}
    cleaned=${cleaned:1}
    if [[ $cleaned == "$content" ]]; then
        [[ $content != *'# >>> Mika CLI >>>'* ]] || warn "Customized Mika setup retained: $file"
        return 0
    fi
    mode=$(stat -f '%Lp' "$file")
    temporary=$(mktemp "$file.mika-uninstall.XXXXXXXX")
    printf '%s' "$cleaned" > "$temporary"
    chmod "$mode" "$temporary"
    mv -f "$temporary" "$file"
    temporary=''
}
for profile in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc" "${ZDOTDIR:-$HOME}/.zshrc"; do clean_profile "$profile"; done
for config in "$HOME/.config" "${XDG_CONFIG_HOME:-$HOME/.config}"; do
    fish=$config/fish/conf.d/mika.fish
    [[ -f $fish && ! -L $fish ]] || continue
    content=''
    if ! IFS= read -r -d '' content < "$fish" && [[ $content == 'fish_add_path --path "$HOME/.local/bin"'$'\n' ]]; then
        rm -f "$fish"
    else warn "Customized Fish setup retained: $fish"; fi
done
command_path=$HOME/.local/bin/mika
if [[ -L $command_path && $(readlink "$command_path") == "$root/bin/mika" ]]; then rm "$command_path"
elif [[ -e $command_path || -L $command_path ]]; then warn "Unrelated command retained: $command_path"; fi
if [[ -d $root ]]; then
    shopt -s nullglob dotglob
    for path in "$root"/*; do
        case ${path##*/} in VERSION|ARCHIVE_SHA256) continue ;; esac
        rm -rf "$path"
    done
    shopt -u nullglob dotglob
    rm -f "$root/VERSION" "$root/ARCHIVE_SHA256"
    rmdir "$root"
fi
if [[ $keep == 0 && -d $models ]]; then
    shopt -s nullglob
    rm -f "$models/$model" "$models/$model".part.*
    shopt -u nullglob
fi
if [[ -d $models ]]; then
    rm -f "$models/.download.lock"
    rmdir "$models" 2>/dev/null || true
fi
if (( locked )); then rmdir "$lock"; locked=0; fi
if [[ -d $parent ]]; then
    rmdir "$parent" 2>/dev/null || warn "Retained models, unrelated files or recovery directories remain in $parent"
fi
printf 'Mika uninstalled. Restart your terminal to refresh command lookup.\n'
