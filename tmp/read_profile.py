#!/usr/bin/env python3
"""Read profile stats and print sorted results."""
import pstats

p = pstats.Stats('profile_current.prof')
p.sort_stats('cumtime').print_stats(25)
p.sort_stats('time').print_stats(15)