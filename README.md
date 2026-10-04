# NuvioTV beta for Downloader

This repository mirrors the **official, universal NuvioTV beta APK** into one GitHub release asset with a fixed URL:

`https://github.com/jamesgallagher/nuvio-beta-downloader/releases/download/beta/NuvioTV-beta-universal.apk`

Create a numeric Downloader code for that URL at [AFTVnews URL Shortener](https://go.aftvnews.com/). Enter the code in Downloader on Android TV whenever you want the newest beta. The code points to the fixed URL; the APK behind it updates automatically. Installing an update still requires opening Downloader and confirming installation on the TV.

The [sync workflow](.github/workflows/sync-beta.yml) checks every three hours and can also be run manually from the Actions tab. It selects the newest published upstream release whose tag contains `beta`, including older NuvioTV releases that were not marked as GitHub prereleases. It requires the exact `app-full-universal-release.apk` asset. Before replacing the mirror it checks the download size, APK archive structure, and SHA-256. The release notes identify the upstream version and source URL. It never builds or re-signs the APK.

The stable link can briefly return an error during asset replacement. If Downloader has trouble following GitHub's download redirects, test the link directly in Downloader before relying on the numeric code.

This is an unofficial mirror of [NuvioTV](https://github.com/NuvioMedia/NuvioTV). The upstream project is GPL-3.0 licensed. Each mirrored release links to the matching upstream source archive and license.

