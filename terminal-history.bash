# terminal-history: shared bash history + fzf-style Ctrl-R picker.
# Source from ~/.bashrc:
#   source /cb/home/jamies/test/terminal-history/terminal-history.bash

_TH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_TH_PICKER="$_TH_DIR/picker.py"

# History settings: big buffer, drop dupes, share across terminals.
HISTSIZE=100000
HISTFILESIZE=200000
HISTCONTROL=ignoredups:ignorespace
HISTTIMEFORMAT='%F %T  '
shopt -s histappend cmdhist

# Append this session's new lines to the file and read new lines from other
# sessions on every prompt -- this is what makes history "shared".
case ":${PROMPT_COMMAND:-}:" in
    *":_th_sync:"*) ;;
    *) PROMPT_COMMAND="_th_sync${PROMPT_COMMAND:+; $PROMPT_COMMAND}" ;;
esac
_th_sync() { history -a; history -n; }

_th_picker_widget() {
    local tmpfile
    tmpfile="$(mktemp -t th_picker.XXXXXX)" || return
    history -a
    python3 "$_TH_PICKER" --query "$READLINE_LINE" --output "$tmpfile"
    if [[ -s "$tmpfile" ]]; then
        READLINE_LINE="$(<"$tmpfile")"
        READLINE_POINT=${#READLINE_LINE}
    fi
    rm -f "$tmpfile"
}

bind -x '"\C-r": _th_picker_widget'
