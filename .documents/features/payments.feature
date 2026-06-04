Feature: Payments
  Staff records payments and closes orders when fully paid.

  Scenario: Customer pays full amount in cash
    Given staff سارا has opened an active order for میز ۱
    And the order total is 300000
    When customer رضا pays 300000 in cash
    Then the paid amount is 300000
    And the unpaid amount is 0
    And the payment method is cash

  Scenario: Customer pays by card
    Given staff سارا has opened an active order for میز ۱
    And the order total is 300000
    When customer رضا pays 300000 by card
    Then the paid amount is 300000
    And the unpaid amount is 0
    And the payment method is card

  Scenario: Two customers split bill via partial payments
    Given staff سارا has opened an active order for میز ۱
    And the order total is 400000
    When customer رضا pays 200000 by card
    And customer نرگس pays 200000 in cash
    Then the paid amount is 400000
    And the unpaid amount is 0
    And the order has 2 payment records

  Scenario: Partial payment leaves table open
    Given staff سارا has opened an active order for میز ۱
    And the order total is 400000
    When customer رضا pays 150000 in cash
    Then the unpaid amount is 250000
    And میز ۱ remains open
    And the order remains active

  Scenario: Full payment closes table
    Given staff سارا has opened an active order for میز ۱
    And the order total is 400000
    When customer رضا pays 400000 by card
    Then the unpaid amount is 0
    And the order is closed
    And میز ۱ becomes empty
