# terminal-history: shared zsh history + fzf-style Ctrl-R picker.
# Source from ~/.zshrc:
#   source /path/to/terminal-history/terminal-history.zsh

_TH_DIR="${0:A:h}"
_TH_PICKER="$_TH_DIR/picker.py"

# History settings: big buffer, drop dupes, share across terminals.
HISTSIZE=100000
SAVEHIST=200000
setopt HIST_IGNORE_DUPS HIST_IGNORE_SPACE HIST_APPEND INC_APPEND_HISTORY SHARE_HISTORY EXTENDED_HISTORY

# Append and read history on every prompt -- makes history "shared".
_th_sync() { fc -AI }
autoload -Uz add-zsh-hook
add-zsh-hook precmd _th_sync

_th_picker_widget() {
    local tmpfile
    tmpfile="$(mktemp)" || return
    fc -AI
    zle -I  # invalidate ZLE display before curses takes over the terminal
    python3 "$_TH_PICKER" --query "$BUFFER" --output "$tmpfile"
    if [[ -s "$tmpfile" ]]; then
        BUFFER="$(<"$tmpfile")"
        CURSOR=${#BUFFER}
    fi
    rm -f "$tmpfile"
    zle reset-prompt
}

zle -N _th_picker_widget
bindkey '^R' _th_picker_widget
