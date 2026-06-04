Feature: Day closing
  Owner closes the business day, creates backups, and syncs when possible.

  Scenario: Owner closes day with all orders settled
    Given owner علی is on the day closing screen
    And all orders for today are closed
    When علی closes the day for 2026-06-04
    Then the day is marked closed
    And no open order remains for 2026-06-04

  Scenario: Owner sees warning when open orders exist
    Given owner علی is on the day closing screen
    And میز ۱ has an active order with unpaid amount 120000
    When علی tries to close the day
    Then the day is not closed
    And علی sees a warning that open orders exist

  Scenario: Day closes successfully without internet
    Given owner علی is on the day closing screen
    And all orders for today are closed
    And the internet connection is unavailable
    When علی closes the day for 2026-06-04
    Then the day is marked closed locally
    And the sync status is pending

  Scenario: Backup created on day close
    Given owner علی is on the day closing screen
    And all orders for today are closed
    When علی closes the day for 2026-06-04
    Then a backup file is created for 2026-06-04
    And the backup includes orders, payments, products, and tables

  Scenario: Only 7 backups kept
    Given 7 backup files already exist
    And owner علی is on the day closing screen
    And all orders for today are closed
    When علی closes the day for 2026-06-04
    Then a new backup file is created for 2026-06-04
    And the oldest backup file is deleted
    And exactly 7 backup files remain

  Scenario: Sync retried after internet restored
    Given the day 2026-06-04 is closed locally
    And the sync status is pending
    And the internet connection is restored
    When the system retries sync
    Then the closed day is sent to the remote server
    And the sync status becomes successful
