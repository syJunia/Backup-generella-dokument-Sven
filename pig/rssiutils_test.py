import settings
import rssiutils as ru
import equiputils as eu

def main():
    print('this test no longer works due to logging compatibility')
    return
    settings.init('server/server_test.cfg')
    print(eu.get_available_observer_names())
    print(ru.get_observer_to_use('tag1'))
    print(ru.get_observer_to_use('tag2'))
    print(ru.get_observer_to_use('tag3'))


if __name__ == "__main__":
    main()

