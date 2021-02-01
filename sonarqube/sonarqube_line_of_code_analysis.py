import argparse
import os
from dataclasses import dataclass

from sonarqube import SonarQubeClient

"""
Measures Lines of Code (LOC) in SonarQube.  

Why:
The SonarQube project overview frontend shows only the size (number of analyzed lines of code) of the default 
branch of a project. There can be very large branches which contribute to the total number of analyzed lines of code
but are not shown in the project overview. 
This script makes it easier to pinpoint projects which contribute most to your total number of analyzed lines of code.
Hence, it is helpful to control the license limits of a SonarQube instance.

How:
The SonarQube REST API is queried to extract the size of each branch of every project in the SonarQube instance.

Features:
* Write each branch name and its number analyzed lines of code of a project to a CSV file.      
* Print the total size (number of analyzed lines of code) of your SonarQube instance. This number should be equal to
  the size reported by SonarQube in the license overview page in the administration section.
* Print the largest files of a branch of a project.

  
Authentication:
Authentication to the SonarQube instance is done via a token with admin privileges.
You have two options to set it:
  * Pass the token via command line with option --sonarqube-admin-token.
  * Set the token as environment variable SONARQUBE_ADMIN_TOKEN.
  
Limitations: 
No exception handling, all exceptions are propagated to the user.

For usage information, call the script with the "--help" option.
"""


@dataclass
class Result:
    """ DTO to represent results for an element that has a number of lines """
    number_of_lines: int
    identifier: str


@dataclass
class BranchResult(Result):
    """ DTO to represent results for an element in a branch """
    branch_name: str


class SonarQubeFacade:
    """ Access SonarQube API """

    def __init__(self, url: str, token: str = ""):
        """
        :parameter url: The address to the sonarQube instance.
        :parameter token A token with admin privileges.
        """
        self.sonarqube_url = url
        self._token = token if token else self._get_token_from_environment_variables()
        self._client = self._create_client()

    def _get_token_from_environment_variables(self):
        """ Retrieve the token from environment variables """
        token = os.getenv("SONARQUBE_ADMIN_TOKEN")
        return token

    def _create_client(self):
        """ Create a SonarQube client """
        return SonarQubeClient(sonarqube_url=self.sonarqube_url, token=self._token)

    def get_project_keys(self):
        """ List the keys of all projects """
        return_object = list(self._client.projects.search_projects())
        return [project["key"] for project in return_object]

    def get_project_size(self, project_key: str):
        """ The the number of lines of code for a specific project """
        component = self._client.measures.get_component_with_specified_measures(component=project_key,
                                                                                metricKeys="ncloc")
        measures = component["component"]["measures"]
        return measures[0]["value"] if len(measures) > 0 else 0

    def get_branches(self, project_key: str):
        """ Retrieve the name of the branches of a project """
        branches = self._client.project_branches.search_project_branches(project=project_key)
        branch_names = [branch["name"] for branch in branches["branches"]]
        return branch_names

    def get_branch_size(self, project_key: str, branch_name: str):
        """ Retrieve the number of lines of a branch of a given project """
        component = self._client.measures.get_component_with_specified_measures(component=project_key,
                                                                                branch=branch_name,
                                                                                metricKeys="ncloc")
        measures = component["component"]["measures"]
        return measures[0]["value"] if len(measures) > 0 else 0

    def get_file_sizes(self, project_key: str, branch_name: str):
        """ Retrieve the file paths and number of lines of a branch for a given project """
        component_tree = list(
            self._client.measures.get_component_tree_with_specified_measures(component=project_key,
                                                                             branch=branch_name,
                                                                             metricKeys="ncloc",
                                                                             strategy="leaves",
                                                                             metricSort="ncloc",
                                                                             asc="false",
                                                                             s="metric"))

        results = [Result(identifier=component["path"], number_of_lines=component["measures"][0]["value"]) for component
                   in component_tree]
        return results


class SonarQubeNumberOfLinesAnalysis:
    """ Analyze the number of lines in SonarQube """

    REPORT_FILE_PATH = "branch_size_report.csv"

    def __init__(self, client: SonarQubeFacade):
        self.client = client

    def get_branch_size_report(self):
        """ Create a report including the name of project, name of branch and the number of lines of code """
        project_keys = self.client.get_project_keys()
        branch_results = []
        for project in project_keys:
            branches = self.client.get_branches(project_key=project)
            for branch in branches:
                code_lines = self.client.get_branch_size(project_key=project, branch_name=branch)
                branch_results.append(
                    BranchResult(identifier=project, branch_name=branch, number_of_lines=int(code_lines)))
        report_string = "Project, Branch, Number of lines of code\n"
        for result in sorted(branch_results, key=lambda x: x.number_of_lines, reverse=True):
            report_string += f"{result.identifier}, {result.branch_name}, {result.number_of_lines}\n"

        return report_string

    def print_in_console_branch_size_report(self):
        """ Print the report of branch size to the console """
        report = self.get_branch_size_report()
        print(report)

    def print_in_file_branch_size_report(self):
        """ Print the report of branch size to a file """
        report = self.get_branch_size_report()
        with open(self.REPORT_FILE_PATH, "w") as file:
            file.write(report)
        print(f"Report written to file {self.REPORT_FILE_PATH}")

    def get_total_size(self):
        """ Get the total number of lines of code """
        project_keys = self.client.get_project_keys()
        total = 0
        for project in project_keys:
            branches = self.client.get_branches(project_key=project)
            number_of_lines = [int(self.client.get_branch_size(project_key=project, branch_name=branch)) for branch in
                               branches]
            total += max(number_of_lines)
        return total

    def get_top_x_files_report(self, project_key: str, branch_name: str, top_x=10):
        """ Retrieve the top x files of a branch """
        file_sizes = self.client.get_file_sizes(project_key=project_key, branch_name=branch_name)
        report = "Project, Branch, Path, Number of lines of code\n"
        for file_size in file_sizes[:top_x]:
            report += f"{project_key}, {branch_name}, {file_size.identifier}, {file_size.number_of_lines}\n"
        return report

    def print_to_console_top_x_files(self, project_key: str, branch_name: str, top_x=10):
        """ Print the results of top x to the console """
        report = self.get_top_x_files_report(project_key, branch_name, top_x)
        print(report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch-size", action="store_true",
                        help="Save the number of lines of code for all branches to a csv file "
                             f"of name {SonarQubeNumberOfLinesAnalysis.REPORT_FILE_PATH}.")
    parser.add_argument("--total-size", action="store_true",
                        help="Print the total size.")
    parser.add_argument("--top-x-files", action="store",
                        help="Get the top x files from a project and branch. x denotes the number of files."
                             " Pass the project, branch, and x as comma separated list, e.g."
                             " --top-x-files=open-source-stack,master,10.")
    parser.add_argument("--sonarqube-admin-token", action="store", default="",
                        help="Token with admin privileges. If no token is passed via command line, "
                             "the script reads the environment variable SONARQUBE_ADMIN_TOKEN.")
    parser.add_argument("--sonarqube-url", action="store", default="https://www.ci-d-fine.de:9000",
                        help="The address of the SonarQube instance.")
    args = parser.parse_args()

    analysis = _create_analysis(args.sonarqube_url, args.sonarqube_admin_token)

    if args.branch_size:
        branch_size_analysis(analysis)
    if args.total_size:
        get_total_size(analysis)
    if args.top_x_files:
        project_key, branch_name, top_x = args.top_x_files.split(",")
        get_top_x(project_key=project_key, branch_name=branch_name, top_x=int(top_x), analysis=analysis)


def _create_analysis(sonarqube_url: str, sonarqube_token: str):
    """ Prepare the analysis object """
    client = SonarQubeFacade(url=sonarqube_url, token=sonarqube_token)
    analysis = SonarQubeNumberOfLinesAnalysis(client=client)
    return analysis


def branch_size_analysis(analysis: SonarQubeNumberOfLinesAnalysis):
    """ Execute the branch size analysis """
    analysis.print_in_file_branch_size_report()


def get_total_size(analysis: SonarQubeNumberOfLinesAnalysis):
    """ Print the total size """
    print(f"Total number of lines: {analysis.get_total_size()}")


def get_top_x(project_key: str, branch_name: str, top_x: int, analysis: SonarQubeNumberOfLinesAnalysis):
    """ Print the top x files from a branch in a give project """
    analysis.print_to_console_top_x_files(project_key, branch_name, top_x)


if __name__ == '__main__':
    main()
