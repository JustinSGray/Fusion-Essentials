"""Boundary-chain placement for Clean Chamfer, free of Fusion and UI imports."""


def place_boundary_edges(edges_to_place, chain_1, chain_2, connected):
    """Extend chain_1/chain_2 at either end with the edges that connect; return the edges that never did."""
    remaining = list(edges_to_place)
    while remaining:
        placed_any = False
        for edge in list(remaining):
            if connected(chain_1[-1], edge):
                chain_1.append(edge)
            elif connected(chain_1[0], edge):
                chain_1.insert(0, edge)
            elif connected(chain_2[-1], edge):
                chain_2.append(edge)
            elif connected(chain_2[0], edge):
                chain_2.insert(0, edge)
            else:
                continue
            remaining.remove(edge)
            placed_any = True
        if not placed_any:
            break
    return remaining


def unplaced_message(count):
    """The refusal Clean Chamfer reports when boundary edges join neither chain."""
    return (f"{count} boundary edge(s) connect to neither chain (an inner loop or branched boundary). "
            "Remove the inner loop or select faces whose boundary is two open chains.")
