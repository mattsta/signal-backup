# This is a utility function to make running the Docker image easier
#
# Source it as follows:
# source helper.sh
#
# And then use it as follows:
# signalexport ~/Downloads/signal-chats/

realpath_local() {
    # From https://stackoverflow.com/a/3572105
    [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
}

signalexport () {
    if [[ -z "$1" ]]; then
        echo 'Must provide output path as first parameters'
        echo 'e.g. signalexport output'
    else
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            input="$HOME/.config/Signal/"
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            input="$HOME/Library/Application Support/Signal/"
        else
            input="$HOME/AppData/Roaming/Signal/"
        fi

        output=$(realpath_local $1)
        shift 1
        docker run --rm -it --name signal-export \
          -v "$input:/Signal" \
          -v "$output:/output" \
          carderne/signal-export:latest $@
    fi
}
