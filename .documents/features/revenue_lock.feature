Feature: Revenue lock
  Revenue on the tables screen is protected until owner authentication succeeds.

  Scenario: Revenue hidden by default on tables screen
    Given owner علی is on the tables screen
    And today's revenue is 2500000
    When the tables screen loads
    Then the revenue amount is hidden
    And a locked revenue indicator is shown

  Scenario: Owner enters correct password to reveal revenue
    Given owner علی is on the tables screen
    And the revenue amount is hidden
    When علی enters the correct revenue password
    Then today's revenue 2500000 is shown
    And the revenue lock is open

  Scenario: Wrong password rejected
    Given owner علی is on the tables screen
    And the revenue amount is hidden
    When علی enters the wrong revenue password
    Then the revenue amount remains hidden
    And علی sees a password error

  Scenario: Revenue auto-hides after timeout
    Given owner علی revealed today's revenue on the tables screen
    And the auto-hide timeout is 60 seconds
    When 60 seconds pass without revenue interaction
    Then the revenue amount is hidden again
    And the revenue lock is closed
