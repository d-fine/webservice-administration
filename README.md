# Webservice Administration

## SonarQube

### Number of analyzed lines of code (LOC)

#### Script
sonarqube/sonarqube_line_of_code_analysis.py

#### Why
The SonarQube project overview frontend shows only the size (number of analyzed lines of code) of the default
branch of a project. There can be very large branches which contribute to the total number of analyzed lines of code
but are not shown in the project overview.
This script makes it easier to pinpoint projects which contribute most to your total number of analyzed lines of code.
Hence, it is helpful to control the license limits of a SonarQube instance.

#### How
The SonarQube REST API is queried to extract the size of each branch of every project in the SonarQube instance.

#### Features
* Write each branch name and its number analyzed lines of code of a project to a CSV file.
* Print the total size (number of analyzed lines of code) of your SonarQube instance. This number should be equal to
  the size reported by SonarQube in the license overview page in the administration section.
* Print the largest files of a branch of a project.
