Feature: QR menu
  Customers view the published menu through a QR code.

  Scenario: Customer scans QR and views menu
    Given the QR menu was published with اسپرسو priced at 120000
    When customer رضا scans the cafe QR code
    Then رضا sees اسپرسو on the QR menu
    And رضا sees the price 120000

  Scenario: QR menu works when cafe laptop is offline
    Given the QR menu was published with اسپرسو priced at 120000
    And the cafe laptop is offline
    When customer رضا opens the QR menu
    Then رضا sees the published menu
    And رضا sees اسپرسو priced at 120000

  Scenario: Menu updates only after manual publish
    Given the QR menu was published with اسپرسو priced at 120000
    And owner علی changes the local price of اسپرسو to 140000
    When customer رضا opens the QR menu before a new publish
    Then رضا still sees اسپرسو priced at 120000
    When علی publishes the menu manually
    And رضا refreshes the QR menu
    Then رضا sees اسپرسو priced at 140000
