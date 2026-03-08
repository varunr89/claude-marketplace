# Spotify Feed Cleanup & Season Organization

## Goal

Clean up test episodes from the podcast RSS feed and organize episodes into Spotify seasons.

## Cleanup: Remove Test Episodes

9 TTS voice comparison episodes from Mar 6 ("Deep RL Intro" with various voice pairs) need to be removed from both the RSS feed and Azure blob storage.

Test episodes to delete:
- Deep RL Intro (Azure: fable/shimmer)
- Deep RL Intro (Azure: nova/onyx)
- Deep RL Intro (Edge: Jenny/Aria)
- Deep RL Intro (Azure: alloy/echo)
- Deep RL Intro (Edge: William/Natasha)
- Deep RL Intro (Edge: Ryan/Sonia)
- Deep RL Intro (Gemini: Fenrir/Leda)
- Deep RL Intro (Gemini: Charon/Aoede)
- Deep RL Intro (Gemini: Puck/Kore)

## Organization: Season Assignments

Using `<itunes:season>` and `<itunes:episode>` tags. Channel-level `<itunes:type>serial</itunes:type>` enables season grouping in Spotify.

| Season | Name | Title Pattern | Content |
|--------|------|---------------|---------|
| 1 | AOSA Vol 2 | `Architecture of Open Source.*Volume 2` | nginx, Open MPI, OSCAR, Puppet, Yesod, etc. |
| 2 | AOSA Performance | `Performance of Open Source` | SocialCalc, Ninja, DAnCE, Zotonic, etc. |
| 3 | 500 Lines or Less | `500 Lines` | 12 episodes from aosabook.org/en/500L/ |
| 4 | Stanford CS234 | `Stanford CS234` | 11 lecture episodes |
| 5 | Sutton & Barto RL | `Reinforcement Learning \(\d+/13\)` | Chapters 1-4 (ongoing) |
| 6 | Articles | Everything else | Paul Graham, Netflix, etc. |

Within each season, episodes numbered chronologically (oldest = Ep 1).

## Implementation: Approach C

1. **Extend `feed.py`** with `remove_episodes()`, `set_episode_season()`, `list_episodes()` functions
2. **Write `cleanup_feed.py`** one-off script that:
   - Downloads `feed.xml` from Azure
   - Removes 9 test episodes
   - Assigns season/episode numbers
   - Sets `<itunes:type>serial</itunes:type>`
   - Uploads updated feed
   - Deletes test audio blobs
   - Supports `--dry-run` (default) and `--apply`
