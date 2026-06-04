Feature: Table management
  Owner manages cafe tables for daily operations.

  Scenario: Owner creates new table
    Given owner علی is on the tables screen
    And no table named میز ۱ exists
    When علی creates a table named میز ۱
    Then میز ۱ is shown on the tables screen
    And میز ۱ is empty

  Scenario: Owner renames table
    Given owner علی is on the tables screen
    And an empty table named میز ۱ exists
    When علی renames میز ۱ to میز پنجره
    Then the tables screen shows میز پنجره
    And the tables screen does not show میز ۱

  Scenario: Owner deletes empty table
    Given owner علی is on the tables screen
    And an empty table named میز ۱ exists
    When علی deletes میز ۱
    Then میز ۱ is removed from the tables screen

  Scenario: Owner cannot delete table with active order
    Given owner علی is on the tables screen
    And میز ۱ has an active order with 1 اسپرسو
    When علی tries to delete میز ۱
    Then the table is not deleted
    And علی sees a warning that میز ۱ has an active order
