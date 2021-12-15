# This is a utility function to make running the Docker image easier
signalexport () {
    if [[ -z "$1" ]]; then
        echo 'Must provide output path as first parameters'
        echo 'e.g. signalexport output'
    else
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            input="~/.config/Signal/"
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            input="~/Library/Application Support/Signal/"
        else
            input="~/AppData/Roaming/Signal/"
        fi

        output=$(readlink -f $1)
        shift 1
        docker run --rm -it --name signal-export \
          -v $input:/Signal \
          -v $output:/output \
          carderne/signal-export:latest $@
    fi
}
