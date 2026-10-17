#!/usr/bin/env bash
# Per-user Linux/WSL installer. Rerun to update; MIKA_REINSTALL=1 forces a repair.
set -euo pipefail

fail() { printf 'mika: %s\n' "$*" >&2; exit 1; }
[[ $(uname -s) == Linux ]] || fail 'Use install.ps1 on Windows.'
[[ $(uname -m) == x86_64 ]] || fail 'Prebuilt releases currently support x86-64 only.'
[[ ${EUID:-$(id -u)} != 0 ]] || fail 'Run this as your normal user, without sudo.'
[[ ${HOME:-} == /* && $HOME != / ]] || fail 'An absolute, non-root HOME directory is required.'
for tool in curl tar sha256sum mktemp grep readlink flock; do
    command -v "$tool" >/dev/null || fail "$tool is required."
done
version=${MIKA_VERSION:-latest}
[[ $version =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail 'Invalid MIKA_VERSION.'
reinstall=${MIKA_REINSTALL:-0}
[[ $reinstall == 0 || $reinstall == 1 ]] || fail 'MIKA_REINSTALL must be 0 or 1.'
asset=mika-linux-x86_64.tar.gz
base=https://github.com/nochinsky/mika/releases
if [[ $version == latest ]]; then base+=/latest/download; else base+=/download/"$version"; fi

data=${XDG_DATA_HOME:-$HOME/.local/share}
[[ $data == /* ]] || data=$HOME/.local/share
parent=$data/mika
root=$parent/app
bin=$HOME/.local/bin
mkdir -p "$parent" "$bin"
exec 9>"$parent/.installer.lock"
flock -n 9 || fail 'Another Mika installer is running. Try again when it finishes.'
[[ ! -e $root || -f $root/VERSION ]] || fail "Refusing to replace an unrelated directory: $root"
if [[ -e $bin/mika || -L $bin/mika ]]; then
    [[ -L $bin/mika && $(readlink "$bin/mika") == "$root/bin/mika" ]] ||
        fail "An unrelated $bin/mika already exists. Move it aside first."
fi
work=$(mktemp -d "$parent/.install.XXXXXXXX")
backup=$work/previous-app
installed=0
success=0
cleanup() {
    local status=$?
    if (( !success )); then
        if { (( installed )) || [[ -e $backup || -L $backup ]]; } && ! rm -rf -- "$root"; then
            printf 'mika: recovery files retained at %s\n' "$work" >&2
            return 1
        fi
        if [[ -e $backup || -L $backup ]]; then
            if ! mv -- "$backup" "$root"; then
                printf 'mika: previous installation retained at %s\n' "$backup" >&2
                return 1
            fi
        fi
    fi
    rm -rf -- "$work" || printf 'mika: could not remove scratch directory %s\n' "$work" >&2
    return "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
fetch() {
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --connect-timeout 30 --max-time "$3" --max-filesize "$4" "$1" --output "$2"
}
printf 'Checking for Mika updates...\n'
# Fetch only the tiny checksum first. The archive fingerprint identifies the exact
# release, including a rebuilt asset whose version label has not changed.
if [[ -n ${MIKA_ARCHIVE_PATH:-} ]]; then
    cp -- "$MIKA_ARCHIVE_PATH.sha256" "$work/$asset.sha256"
else
    fetch "$base/$asset.sha256" "$work/$asset.sha256" 60 4096
fi
read -r expected _ < "$work/$asset.sha256"
[[ $expected =~ ^[0-9a-fA-F]{64}$ ]] || fail 'Invalid release checksum file.'
expected=${expected,,}
current=0
installed_version=''
if [[ -f $root/VERSION ]]; then installed_version=$(<"$root/VERSION"); fi
if [[ $reinstall == 0 && -f $root/ARCHIVE_SHA256 && -x $root/bin/mika &&
      $(<"$root/ARCHIVE_SHA256") == "$expected" ]]; then
    if actual=$("$root/bin/mika" --version 2>/dev/null) && [[ $actual == "mika ${installed_version#v}" ]]; then
        current=1
    fi
fi
if (( current )); then
    message="Mika ${installed_version#v} is already up to date."
else
    if [[ -n ${MIKA_ARCHIVE_PATH:-} ]]; then cp -- "$MIKA_ARCHIVE_PATH" "$work/$asset"
    else fetch "$base/$asset" "$work/$asset" 600 268435456; fi
    (cd "$work" && printf '%s  %s\n' "$expected" "$asset" | sha256sum --check --status) ||
        fail 'Release checksum mismatch. Existing installation unchanged.'
    while IFS= read -r entry; do
        [[ $entry == mika/* && $entry != *'/../'* && $entry != */.. ]] || fail 'Unsafe release archive path.'
    done < <(tar -tzf "$work/$asset")
    tar -xzf "$work/$asset" --no-same-owner --no-same-permissions -C "$work"
    candidate=$work/mika
    [[ -f $candidate/VERSION && -x $candidate/bin/mika ]] || fail 'Incomplete release package.'
    candidate_version=$(<"$candidate/VERSION")
    [[ $candidate_version =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail 'Invalid package version.'
    actual=$("$candidate/bin/mika" --version) || fail 'This binary cannot start. Linux glibc 2.35+ is required.'
    [[ $actual == "mika ${candidate_version#v}" ]] || fail 'Package version does not match its binary.'
    printf '%s\n' "$expected" > "$candidate/ARCHIVE_SHA256"
    if [[ -e $root || -L $root ]]; then mv -- "$root" "$backup"; fi
    # Mark intent before the move: a signal can arrive immediately after it.
    installed=1
    mv -- "$candidate" "$root"
    "$root/bin/mika" --version >/dev/null || fail 'Installed binary failed its startup check.'
    if [[ -n $installed_version && $installed_version != "$candidate_version" ]]; then
        message="Updated Mika ${installed_version#v} -> ${candidate_version#v}."
    elif [[ -n $installed_version ]]; then message="Reinstalled Mika ${candidate_version#v}."
    else message="Installed Mika ${candidate_version#v}."; fi
fi
ln -sfn -- "$root/bin/mika" "$bin/mika"
success=1

# A piped child cannot alter its parent's PATH. Configure future interactive shells.
path_block='# >>> Mika CLI >>>
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
# <<< Mika CLI <<<'
add_profile() {
    local file=$1
    if ! grep -Fq '# >>> Mika CLI >>>' "$file" 2>/dev/null; then
        printf '\n%s\n' "$path_block" >> "$file" ||
            printf 'mika: add ~/.local/bin to PATH manually; could not update %s\n' "$file" >&2
    fi
}
shell_name=${SHELL:-/bin/bash}
case ${shell_name##*/} in
    zsh) add_profile "${ZDOTDIR:-$HOME}/.zshrc" ;;
    fish)
        fish_dir=${XDG_CONFIG_HOME:-$HOME/.config}/fish/conf.d
        if mkdir -p "$fish_dir" && [[ ! -e $fish_dir/mika.fish ]]; then
            printf '%s\n' 'fish_add_path --path "$HOME/.local/bin"' > "$fish_dir/mika.fish" || true
        fi ;;
    *) add_profile "$HOME/.bashrc"; add_profile "$HOME/.profile" ;;
esac
printf '%s\n' "$message"
case ":${PATH:-}:" in
    *":$bin:"*) printf 'Run: mika\n' ;;
    *) printf 'Restart your terminal, then run: mika\n'
       printf 'Or activate now: export PATH="$HOME/.local/bin:$PATH"\n' ;;
esac
