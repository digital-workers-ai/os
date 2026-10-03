The review queue this week

What changed: look-alike records now wait in a review queue. Sales has one Acme, billing has another, support has a third. DW-OS puts the pair in front of a person, who confirms, rejects or splits them. Nothing merges on its own.

What it rests on: raw data is kept exactly as it arrived. A rebuild wipes the derived layer and recomputes it from the raw store, so a wrong decision is undone by rejecting it and rebuilding.

What to do: open the queue in the console, read the evidence on each pair, and decide. The decisions survive every rebuild.
