import ast
import os


def env(key, default=None, required=True):
    """
    Retrieves environment variables and returns Python natives. The (optional)
    default will be returned if the environment variable does not exist.
    """
    try:
        value = os.environ[key]
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value
    except KeyError:
        if default or not required:
            return default
        raise RuntimeError("Missing required environment variable '%s'" % key)


DATABASE_USERNAME = env('ZOCDOC_DATABASE_USERNAME', 'neo4j')
DATABASE_PASSWORD = env('ZOCDOC_DATABASE_PASSWORD', 'cherhuang')
DATABASE_URL = env('ZOCDOC_DATABASE_URL', 'bolt://localhost:7687')
