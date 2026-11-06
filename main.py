if __name__ == '__main__':
    from src.bootstrap import prepare_environment
    prepare_environment()
    from multiprocessing import freeze_support
    freeze_support()
    from src.config_migration import apply_pending_migration
    apply_pending_migration()
    from config import config
    from ok import OK

    config = config
    ok = OK(config)
    ok.start()
