Part 2
------
CLI Command:
Part2.py [Command] [Ratings] [k] [t] [e] [u] [v] [b]
             [-t [T]] [-e [E]] [-u [U]] [-v [V]] [-b [B]]
How to use:
In order to run the web service with default paths, run python Part2.py
In order to run the web service with different paths, use the -u, -v and -b flags.

Mandatory arguments:
Command: 'ExtractCB', any other input will not start the recommendation system build but will start the web service
Ratings: Path to ratings file. File name must be 'ratings.csv'.

Optional arguments:
*** Important ***
In order to use some of the optional arguments, insert the first arguments in the order of the command.
When you reach an argument you don't want to insert, leave it blank but use the rest of the arguments with the appropriate flag!
If you entered an argument in its order and with a flag, the value in the flag will be used
For example, if I want t & e to set to default values only I will use:
Part2.py ExtractCB ./ratings.csv 10 -u ./uFolder -v ./vFolder -b ./bFolder

k: K size, default 20
t: T size, default 10
e: Epsilon, default 0.01
u: U file path. default: u1.csv
v: V file path. default: v1.csv
b: B file path. default: b1.csv