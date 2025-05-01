class InitializeError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class ServerConfigNotInitialized(InitializeError):
    def __init__(self):
        super().__init__("Server Config must be initialized first")


class UnableToGetEnvVariable(InitializeError):
    def __init__(self, variables: tuple[str]):
        super().__init__(f"Unable to get the Env variables: {variables}")


class UnableToInitializeService(InitializeError):
    def __init__(self, service_name: str):
        super().__init__(f"Unable to initialize [{service_name}]")


class ConfigNotInitalizedButUsing(InitializeError):
    def __init__(self, config_name: str):
        super().__init__(
            f"Config [{config_name}] has not been initialized, but is being used"
        )


class UnableToInitalizeDatabase(InitializeError):
    def __init__(self):
        super().__init__("Unable to initalize database")


class DatabaseNotInitialized(InitializeError):
    def __init__(self):
        super().__init__("Database has not beed initialized, but is being user")
