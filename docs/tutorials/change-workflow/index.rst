.. _change_workflow_tutorial:

Change workflow in CNaaS-NMS
============================

Changing the active configuration of devices managed by CNaaS involves several steps.
It might seem complicated if you just need to make a single small change, but it's a very
powerful tool for keeping the entire network synchronized to your ideal configuration state.
Hopefully our web frontend will help make things easier by providing a workflow system for
common tasks.

The are five basic steps to commiting a change to the network:

#. Update git repository and commit/push
#. Ask CNaaS to pull latest git repo change (refresh)
#. Do a dry_run to get a diff for all affected devices
#. Look through and verify diff outputs
#. If everything looks good, commit configuration to devices

Client facing interfaces on access switches can be changed in a web interface without the need
for using Git to make it easier for helpdesk/servicedesk/NOC etc to make smaller changes.
If a change only impacts one device and has a very low "change impact score" (more on this later)
you can also simplify the workflow above and skip the steps of manual verification of the diff
and manual push to commit configuration to devices. In this case, the workflow could look
like this:

#. Update port setting in web frontend and click "save"
#. CNaaS does dry run and calculates "change impact score". If score is less than 10 a live run
   will automatically be triggered to run immediately after.

.. _change_impact_score:

Change impact score
-------------------

The change impact score is an attempt from the CNaaS-NMS software to estimate how risky
a particular change (sync) operation might be. It's currently very primitive and has no deeper
intelligence, it just calculates number of lines changed and does text pattern matching to try
and identify important lines in the configuration. The score calculated for a particular
sync job is between 1 and 100 where 1 signifies a very small risk and 100 a very big risk.
Configuration lines relating to the description of an interface has a modifier to make it
have a very low score, and configuration lines that will remove an IP-address from an interface
for example will get a much higher score. Exactly how the score is calculated and what text
patterns are being searched for can be found in the file changescore.py in the source code.
