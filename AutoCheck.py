import requests

# Function to get the latest release or pre-release from GitHub
def get_latest_release(repo_owner, repo_name, include_prereleases=False):
    # GitHub API endpoint for releases
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
    
    # Send a request to the GitHub API
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        releases = response.json()

        # Check if the releases list is empty
        if not releases:
            print("No releases found for this repository.")
            return
        
        # Filter releases if we need pre-releases as well
        if include_prereleases:
            latest_release = releases[0]
        else:
            # Filter to get the latest stable release
            latest_release = next((release for release in releases if not release['prerelease']), None)

        if latest_release:
            print(f"Latest release version: {latest_release['tag_name']}")
            print(f"Release Name: {latest_release['name']}")
            print(f"Release URL: {latest_release['html_url']}")
        else:
            print("No stable release found.")
    else:
        print(f"Failed to fetch releases. Status code: {response.status_code}")

def main():
    # Example usage
    repo_owner = "MrAndiGamesDev"  # Replace with the repository owner's username
    repo_name = "NEW-Roblox-Transaction-Balance-Monitor"  # Replace with the repository name
    include_prereleases = True  # Set to True if you want pre-releases too

    get_latest_release(repo_owner, repo_name, include_prereleases)

if __name__ == "__main__":
    main()