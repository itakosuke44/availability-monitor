"""Stop monitoring after the configured final day in Japan."""
import os
from datetime import datetime
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

END_EXCLUSIVE = datetime(2026, 11, 20, tzinfo=ZoneInfo('Asia/Tokyo'))


def is_active(now=None):
    return (now or datetime.now(ZoneInfo('Asia/Tokyo'))) < END_EXCLUSIVE


def main():
    active = is_active()
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('active=' + str(active).lower() + '\n')
    if active:
        print('Monitoring is within the configured period.')
        return
    print('Monitoring period ended. No calendar requests or email will be sent.')
    repository = os.environ['GITHUB_REPOSITORY']
    request = Request(
        'https://api.github.com/repos/' + repository + '/actions/workflows/monitor.yml/disable',
        method='PUT',
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28'})
    with urlopen(request, timeout=30) as response:
        if response.status != 204:
            raise RuntimeError('Could not disable expired workflow.')
    print('Workflow disabled; source files retained.')


if __name__ == '__main__':
    main()
