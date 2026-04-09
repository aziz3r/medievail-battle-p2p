from model.scenarios import scenario_lanchester


def main():
    try:
        from view.terminal_view import TerminalView
    except ModuleNotFoundError as exc:
        if exc.name == "_curses":
            print("Terminal View indisponible: module _curses manquant.")
            print("Sous Windows, installez-le avec: pip install windows-curses")
            return
        raise

    game = scenario_lanchester("knight", 50)
    view = TerminalView(game)
    view.start()


if __name__ == "__main__":
    main()
